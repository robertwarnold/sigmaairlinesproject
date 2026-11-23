"""Supported GitHub REST synchronization; read-only and never dispatches generation."""
import io
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import urllib.error
from urllib.parse import urlencode
import urllib.request
import zipfile

from .registry import workflow_key, now, encoded


class RateLimited(RuntimeError):
    def __init__(self,retry_after=None):
        super().__init__('GitHub rate limit; retry synchronization later (no model call made)')
        self.retry_after=retry_after


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs): return None


class GitHub:
    def __init__(self,token=None): self.token=token or os.getenv('GH_TOKEN') or os.getenv('GITHUB_TOKEN')
    def get(self,path,binary=False):
        if not path.startswith('/repos/'): raise ValueError('GitHub repository endpoint required')
        headers={'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'sigma-research-registry'}
        if self.token: headers['Authorization']='Bearer '+self.token
        request=urllib.request.Request('https://api.github.com'+path,headers=headers)
        try:
            with urllib.request.build_opener(NoRedirect).open(request,timeout=30) as response: content=response.read(100_000_001)
        except urllib.error.HTTPError as exc:
            if exc.code in (403,429) and (exc.headers.get('Retry-After') or exc.headers.get('X-RateLimit-Remaining')=='0' or exc.code==429):
                raise RateLimited(exc.headers.get('Retry-After') or exc.headers.get('X-RateLimit-Reset')) from None
            if binary and exc.code==302:
                url=exc.headers['Location']
                if not url.startswith('https://'): raise ValueError('Insecure artifact redirect')
                # Signed storage redirect must never receive the GitHub Authorization header.
                with urllib.request.urlopen(url,timeout=60) as response: content=response.read(100_000_001)
            else: raise RuntimeError('GitHub API HTTP '+str(exc.code)) from None
        if len(content)>100_000_000: raise ValueError('Artifact exceeds sync size limit')
        return content if binary else json.loads(content)
    def pages(self,path,key):
        page=1
        while True:
            separator='&' if '?' in path else '?'
            response=self.get(path+separator+f'per_page=100&page={page}')
            records=response if key is None else response[key]
            yield from records
            if len(records)<100: break
            page+=1


def repository_root(repository):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository):
        raise ValueError('Invalid repository')
    return f'/repos/{repository}'


def discover_branches(repository, client=None):
    root=repository_root(repository)
    return [{'branch': entry['name'], 'commit': entry['commit']['sha']}
            for entry in (client or GitHub()).pages(root+'/branches', None)]


def archive_generated_members(store, archive, receipt_member, receipt, generation_id):
    """Preserve receipt-bound generator files without extracting arbitrary ZIP paths."""
    parent = PurePosixPath(receipt_member).parent
    records = []
    for name, declared in receipt.get('artifacts', {}).items():
        if not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:csv|json|xlsx|txt)', name):
            continue
        stem = PurePosixPath(receipt_member).name.removesuffix('_execution.json')
        if name not in {stem + suffix for suffix in ('.csv', '.json', '.xlsx', '_raw.txt','_diagnostics.json')}:
            continue
        member = str(parent / name)
        matches = [entry for entry in archive.infolist() if entry.filename == member]
        if not matches:
            continue
        if len(matches) != 1 or matches[0].file_size > 20_000_000:
            raise ValueError('Duplicate or oversized generated artifact')
        with archive.open(matches[0]) as stream:
            content = stream.read(20_000_001)
        sha = hashlib.sha256(content).hexdigest()
        if len(content)>20_000_000 or declared.get('sha256')!=sha or declared.get('bytes')!=len(content):
            raise ValueError('Generated artifact differs from its execution receipt')
        path = store.raw / (sha + PurePosixPath(name).suffix)
        if not path.exists():
            path.write_bytes(content)
        records.append({'generation_id':generation_id,'member':member,'sha256':sha,'bytes':len(content)})
    return records


def import_engineering_run(store, engineering, archive, receipt_path, receipt, members):
    if receipt.get('prompt_version')!='v4.0' or receipt.get('status')!='success':
        return None
    responses = [entry for entry in members if entry['member'].endswith(('_raw.txt','.json'))
                 and not entry['member'].endswith('_diagnostics.json')]
    if len(responses)!=1 or not receipt.get('inventory_sha256'):
        return None
    candidates = [entry for entry in archive.infolist()
                  if PurePosixPath(entry.filename).name=='input_inventory.json' and entry.file_size<=2_000_000]
    for candidate in candidates:
        content = archive.read(candidate)
        if hashlib.sha256(content).hexdigest()!=receipt['inventory_sha256']:
            continue
        inventory = store.raw / (receipt['inventory_sha256'] + '.json')
        if not inventory.exists():
            inventory.write_bytes(content)
        response = responses[0]
        source = store.raw / (response['sha256'] + PurePosixPath(response['member']).suffix)
        return engineering.ingest(source,inventory,receipt_path,'sha256:'+receipt['system_sha256'])
    return None


def synchronize(store,repository,client=None,run_id=None,download=True,branches=(),engineering=None):
    """Backfill workflows, receipts and verified generated ZIP members.

    No HTML scraping, log scraping, model calls, retries or assumed generations.
    Re-running is idempotent. A rate limit preserves prior committed data and records
    the error without advancing the last-successful synchronization timestamp.
    """
    client=client or GitHub()
    root=repository_root(repository); problems=[]; receipts=0
    if run_id and branches:
        raise ValueError('Select a workflow run or a set of branches')
    try:
        workflow=root+'/actions/workflows/generate-fmea.yml/runs'
        if run_id:
            runs=[client.get(root+f'/actions/runs/{int(run_id)}')]
        else:
            queries=[workflow+'?'+urlencode({'branch': branch}) for branch in dict.fromkeys(branches)] or [workflow]
            runs=(run for query in queries for run in client.pages(query,'workflow_runs'))
        for run in runs:
            current_key=workflow_key(repository,run['id'],int(run.get('run_attempt',1)))
            cached=store.db.execute('SELECT * FROM sync_runs WHERE execution_id=?',(current_key,)).fetchone()
            cache_version=3 if engineering else 2
            if cached and run.get('status')=='completed' and cached['updated_at']==run.get('updated_at') and (not download or cached['artifacts_complete']>=cache_version): continue
            artifact_failures=False
            for attempt in range(1,int(run.get('run_attempt',1))+1):
                record=run if attempt==int(run.get('run_attempt',1)) else client.get(root+f'/actions/runs/{run["id"]}/attempts/{attempt}')
                jobs=list(client.pages(root+f'/actions/runs/{run["id"]}/attempts/{attempt}/jobs','jobs'))
                record['job_ids']=[j['id'] for j in jobs]
                with store.transaction():
                    execution=store.workflow(repository,record)
                    title=record.get('display_title','')
                    for planned in store.db.execute("SELECT id,payload FROM generations WHERE state='PLANNED'").fetchall():
                        payload=json.loads(planned['payload'])
                        if payload['run_id'] and re.search(r'(?<![A-Za-z0-9_-])'+re.escape(payload['run_id'])+r'(?![A-Za-z0-9_-])',title):
                            payload['workflow_execution_id']=execution
                            store.db.execute('UPDATE generations SET workflow_id=?,payload=? WHERE id=?',(execution,encoded(payload),planned['id']))
                            store.transition(planned['id'],'QUEUED',{'workflow_execution_id':execution})
            for artifact in client.pages(root+f'/actions/runs/{run["id"]}/artifacts','artifacts'):
                aid=str(artifact['id']); metadata={'artifact_id':aid,'name':artifact['name'],'expired':artifact.get('expired',False),'download_status':'metadata_only','workflow_run_id':str(run['id'])}
                prior=store.db.execute('SELECT payload FROM artifacts WHERE id=?',(repository+':'+aid,)).fetchone()
                if prior:
                    cached_artifact=json.loads(prior[0])
                    if 'generated_members' in cached_artifact and (not engineering or 'engineering_runs' in cached_artifact): continue
                if metadata['expired']: problems.append({'artifact_id':aid,'reason':'expired'})
                elif download:
                    try:
                        payload=client.get(root+f'/actions/artifacts/{int(aid)}/zip',binary=True)
                        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                            entries=archive.infolist()
                            if len(entries)>4096 or sum(entry.file_size for entry in entries)>100_000_000:
                                raise ValueError('Artifact exceeds expansion limits')
                            members=[m for m in archive.infolist() if m.filename.endswith('_execution.json')]
                            generated_members=[]
                            engineering_runs=[]
                            if sum(m.file_size for m in members)>20_000_000: raise ValueError('Receipt payload too large')
                            for member in members:
                                if member.file_size>2_000_000: raise ValueError('Receipt exceeds size limit')
                                content=archive.read(member); receipt=json.loads(content)
                                if receipt.get('workflow')!='standalone_gemini': continue
                                destination=store.raw/(hashlib.sha256(content).hexdigest()+'_execution.json')
                                if not destination.exists(): destination.write_bytes(content)
                                receipt_attempt=receipt.get('github',{}).get('run_attempt')
                                match=re.fullmatch(r'fmea-results-'+str(run['id'])+r'-(\d+)',artifact['name'])
                                if receipt_attempt is None and match: receipt_attempt=int(match[1])
                                if receipt_attempt is None and int(run.get('run_attempt',1))==1: receipt_attempt=1
                                execution=workflow_key(repository,run['id'],int(receipt_attempt)) if receipt_attempt else None
                                if execution is None: problems.append({'artifact_id':aid,'reason':'workflow attempt not verifiable from legacy artifact'})
                                with store.transaction():
                                    gid=store.receipt(destination,execution,artifact=aid)
                                    values=archive_generated_members(store,archive,member.filename,receipt,gid)
                                    generated_members.extend(values)
                                if engineering:
                                    key=import_engineering_run(store,engineering,archive,destination,receipt,values)
                                    if key:
                                        engineering_runs.append(key)
                                receipts+=1
                        metadata['download_status']='downloaded'; metadata['receipt_members']=len(members)
                        metadata['generated_members']=generated_members
                        if engineering:
                            metadata['engineering_runs']=engineering_runs
                    except RateLimited: raise
                    except Exception as exc:
                        metadata['download_status']='failed'; artifact_failures=True; problems.append({'artifact_id':aid,'reason':type(exc).__name__})
                with store.transaction():
                    execution=workflow_key(repository,run['id'],int(run.get('run_attempt',1)))
                    store.db.execute('INSERT INTO artifacts VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(repository+':'+aid,execution,encoded(metadata)))
            if run.get('status')=='completed':
                store.db.execute('INSERT INTO sync_runs VALUES(?,?,?) ON CONFLICT(execution_id) DO UPDATE SET updated_at=excluded.updated_at,artifacts_complete=excluded.artifacts_complete',(current_key,run.get('updated_at'),cache_version*int(download and not artifact_failures)))
        previous=store.db.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()
        state={'last_successful_sync':(json.loads(previous[0]).get('last_successful_sync') if previous else None) if problems else now(),'status':'PARTIAL' if problems else 'SUCCESS','problems':problems,'receipt_members_processed':receipts}
        store.db.execute('INSERT INTO sync_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(encoded(state),))
        return state
    except RateLimited as exc:
        prior=store.db.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()
        state={'last_successful_sync':json.loads(prior[0]).get('last_successful_sync') if prior else None,'status':'RATE_LIMITED','retry_after':exc.retry_after,'problems':problems}
        store.db.execute('INSERT INTO sync_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(encoded(state),))
        return state

    except (urllib.error.URLError, OSError, RuntimeError) as exc:
        prior=store.db.execute('SELECT payload FROM sync_state WHERE id=1').fetchone()
        state={'last_successful_sync':json.loads(prior[0]).get('last_successful_sync') if prior else None,
               'status':'SYNC_ERROR','error_type':type(exc).__name__,'problems':problems}
        store.db.execute('INSERT INTO sync_state VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',(encoded(state),))
        return state
