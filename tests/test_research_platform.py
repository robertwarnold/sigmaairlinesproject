"""Synthetic registry/GitHub/judge/finance tests: never research observations."""
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from unittest.mock import patch

from analysis.research.registry import Registry, workflow_key
from analysis.research.github_sync import synchronize, RateLimited
from analysis.research.judge_import import adapt
from analysis.research.platform import snapshot
from analysis.research.finance import model, DEFAULTS
from analysis.research.__main__ import empty_snapshot, validate_snapshot
from test_v4 import import_data


def receipt(root,attempt='a',system='A',workflow=None,status='success',rows=2):
    data={'workflow':'standalone_gemini','experiment_id':'synthetic-test','attempt_id':attempt,
          'source_attempt_id':attempt,'system_id':'system_'+system,'prompt_version':'v4.0',
          'model':'synthetic-only','configuration':{'temperature':0},'status':status,
          'started_at':'2026-11-15T10:00:00+00:00','finished_at':'2026-11-15T10:01:00+00:00',
          'row_count':rows if status=='success' else None,'api_request_seconds':60,
          'data_origin':'synthetic_test','completeness':{'structural_status':'PASS'}}
    if workflow: data['github']=workflow
    path=root/(attempt+'_execution.json'); path.write_text(json.dumps(data)); return path


def workflow(run=1,attempt=1,status='completed',conclusion='success'):
    return {'id':run,'run_attempt':attempt,'name':'Generate FMEA with shared Gemini key','status':status,'conclusion':conclusion,
            'html_url':f'https://github.com/test/repo/actions/runs/{run}','created_at':'2026-11-15T10:00:00Z','updated_at':'2026-11-15T10:02:00Z'}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='results'); self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name); self.store=Registry(self.root/'registry.sqlite'); self.addCleanup(self.store.close)

    def register(self,**kwargs):
        path=receipt(self.root,**kwargs)
        with self.store.transaction(): gid=self.store.receipt(path)
        return gid

    def judge(self,gid):
        data=import_data(); data['runs'][0]['run_id']=gid; data['runs'][0]['evaluation_timestamp']='2026-11-15T12:00:00+00:00'
        return data

    def accept(self,data):
        path=self.root/'judge_import.json'; path.write_text(json.dumps(data)); return self.store.accept(data,path)

    def test_batch_generation_workflow_retries_and_idempotency(self):
        with self.store.transaction():
            key=self.store.workflow('test/repo',workflow())
            gid=self.store.receipt(receipt(self.root,'a'),key)
            gid2=self.store.receipt(receipt(self.root,'b',system='B'),key)
            self.assertEqual(gid,self.store.receipt(self.root/'a_execution.json',key))
            key2=self.store.workflow('test/repo',workflow(attempt=2))
        self.assertNotEqual(gid,gid2); self.assertNotEqual(key,key2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM generations').fetchone()[0],2)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM workflows').fetchone()[0],2)
        self.assertEqual(self.store.generation(gid)['state'],'AWAITING_JUDGE')
        self.assertEqual(self.store.reconcile()['evaluations_without_generation'],0)

    def test_valid_judge_repeated_evaluations_preserved_explicit_selection(self):
        gid=self.register(); data=self.judge(gid)
        previews=self.accept(data); first=previews[0]['evaluation_id']
        self.assertEqual(self.store.generation(gid)['state'],'HUMAN_REVIEW_PENDING')
        self.assertTrue(self.accept(data)[0]['duplicate'])
        second=copy.deepcopy(data); second['runs'][0]['evaluation_id']='second-judge'; second['runs'][0]['evaluation_timestamp']='2026-11-16T12:00:00+00:00'
        self.accept(second)
        self.assertEqual(self.store.generation(gid)['selected_evaluation'],first)
        self.store.select(gid,'second-judge')
        self.assertEqual(self.store.generation(gid)['selected_evaluation'],'second-judge')
        self.assertEqual(len(self.store.selected()),1)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM evaluations').fetchone()[0],2)

    def test_invalid_or_mismatched_import_rolls_back(self):
        gid=self.register(); good=self.judge(gid)
        for mutation in ('run','system','version','rows','items','model'):
            data=copy.deepcopy(good); run=data['runs'][0]
            if mutation=='run': run['run_id']='unknown'
            if mutation=='system': run['system']='B'
            if mutation=='version': run['skill_version']='v2.0'
            if mutation=='rows': run['generated_rows']=999
            if mutation=='items': run['items'][0]['found']='true'
            if mutation=='model': run['generator_model']='other'
            with self.subTest(mutation=mutation),self.assertRaises(ValueError): self.accept(data)
            self.assertEqual(self.store.db.execute('SELECT count(*) FROM evaluations').fetchone()[0],0)
            self.assertEqual(self.store.generation(gid)['state'],'AWAITING_JUDGE')

    def test_failed_run_never_gets_quality_and_snapshot_is_sanitized(self):
        gid=self.register(status='failed')
        with self.assertRaises(ValueError): self.accept(self.judge(gid))
        data=snapshot(self.store,self.root/'current.json',render=False)
        validate_snapshot(data)
        self.assertEqual(data['operations']['failed_generations'],1)
        self.assertIsNone(data['registry'][0]['missed_percentage'])
        self.assertEqual(data['runs'],[])
        self.assertNotIn('receipt_path',json.dumps(data))
        before=(self.root/'current.json').read_bytes()
        with patch('analysis.research.platform.subprocess.run',side_effect=RuntimeError('renderer failed')):
            with self.assertRaises(RuntimeError): snapshot(self.store,self.root/'current.json',render=True)
        self.assertEqual(before,(self.root/'current.json').read_bytes())

    def test_selected_quality_uses_existing_denominators_and_preserves_notes_privately(self):
        gid=self.register(); self.accept(self.judge(gid))
        data=snapshot(self.store,self.root/'current.json',render=False)
        self.assertEqual(data['runs'][0]['missed_percentage'],50)
        self.assertEqual(data['runs'][0]['dpmo'],500000)
        self.assertEqual(data['operations']['evaluated_fmeas'],1)
        self.assertNotIn('PRIVATE_SENTINEL',json.dumps(data))
        self.assertNotIn('judge_notes',json.dumps(data))
        self.assertEqual(data['financial']['status'],'MODELED_NOT_MEASURED')

    def test_csv_and_workbook_adapters(self):
        gid=self.register(); data=self.judge(gid)
        from analysis.round2.__main__ import write_csv
        run=data['runs'][0]; metadata={k:v for k,v in run.items() if k!='items'}
        write_csv(self.root/'runs.csv',[metadata]); write_csv(self.root/'items.csv',[{'run_id':gid,**i} for i in run['items']])
        parsed=adapt(self.root/'runs.csv',self.root/'items.csv'); self.store.preview(parsed)
        import pandas as pd
        with pd.ExcelWriter(self.root/'analysis.xlsx',engine='xlsxwriter') as writer:
            pd.DataFrame([{k:json.dumps(v) if isinstance(v,dict) else v for k,v in metadata.items()}]).to_excel(writer,sheet_name='runs',index=False)
            pd.DataFrame([{'run_id':gid,**i} for i in run['items']]).to_excel(writer,sheet_name='items',index=False)
        parsed=adapt(self.root/'analysis.xlsx'); self.store.preview(parsed)

    def test_planned_run_receipt_links_without_duplicate_generation(self):
        manifest=self.root/'manifest.json'; manifest.write_text(json.dumps({'generator_model':'synthetic-only','runs':[{'run_id':'round2-v4-A-r01','system':'A','skill_version':'v4.0','replicate':1}]}))
        self.store.plan(manifest)
        path=receipt(self.root); data=json.loads(path.read_text()); data['study_run_id']='round2-v4-A-r01'; path.write_text(json.dumps(data))
        self.store.receipt(path)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM generations').fetchone()[0],1)

    def test_invalid_generated_output_has_validation_failed_lifecycle(self):
        path=receipt(self.root,status='failed'); data=json.loads(path.read_text()); data['failure_classification']='truncation'; path.write_text(json.dumps(data))
        with self.store.transaction(): gid=self.store.receipt(path)
        self.assertEqual(self.store.generation(gid)['state'],'VALIDATION_FAILED')
        self.assertEqual(self.store.selected(),[])

    def test_failed_workflow_does_not_invent_a_generation(self):
        with self.store.transaction(): self.store.workflow('test/repo',workflow(status='completed',conclusion='failure'))
        data=snapshot(self.store,self.root/'current.json',render=False)
        self.assertEqual(data['operations']['registered_generations'],0)
        self.assertEqual(data['operations']['evaluated_fmeas'],0)
        self.assertEqual(data['workflow_executions'][0]['conclusion'],'failure')

    def test_conflicting_evaluation_id_and_batch_selection(self):
        gid=self.register(); data=self.judge(gid)
        first=copy.deepcopy(data['runs'][0]); first['evaluation_id']='first'
        second=copy.deepcopy(first); second['evaluation_id']='second'
        batch={**data,'runs':[first,second]}; self.accept(batch)
        self.assertEqual(self.store.generation(gid)['selected_evaluation'],'first')
        conflict={**data,'runs':[copy.deepcopy(first)]}; conflict['runs'][0]['evaluation_timestamp']='different'
        with self.assertRaisesRegex(ValueError,'Conflicting'): self.accept(conflict)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM evaluations').fetchone()[0],2)

    def test_human_review_completion_is_a_separate_idempotent_event(self):
        gid=self.register(); self.accept(self.judge(gid))
        self.store.human_review(gid,'review-1','complete','2026-11-15T14:00:00+00:00',12)
        self.store.human_review(gid,'review-1','complete','2026-11-15T14:00:00+00:00',12)
        self.assertEqual(self.store.generation(gid)['state'],'COMPLETE')
        data=snapshot(self.store,self.root/'current.json',render=False)
        self.assertEqual(data['financial']['measured']['recorded_review_minutes'],12)
        self.assertEqual(len(data['evaluations']),1)

    def test_csv_duplicate_headers_rejected(self):
        source=self.root/'runs.csv'; source.write_text('run_id,run_id\na,b\n')
        items=self.root/'items.csv'; items.write_text('run_id,item_id,found\na,i,true\n')
        with self.assertRaisesRegex(ValueError,'duplicate'): adapt(source,items)

    def test_retried_workflow_counts_only_new_receipt_as_new_generation(self):
        with self.store.transaction():
            key=self.store.workflow('test/repo',workflow()); path=receipt(self.root)
            first=self.store.receipt(path,key)
            key2=self.store.workflow('test/repo',workflow(attempt=2))
            self.assertEqual(self.store.receipt(path,key2),first)
            content=json.loads(path.read_text()); content['started_at']='2026-11-16T10:00:00+00:00'; path.write_text(json.dumps(content))
            second=self.store.receipt(path,key2)
        self.assertNotEqual(first,second)
        with self.assertRaisesRegex(ValueError,'ambiguous'): self.store.resolve('synthetic-test:a')

    def test_receipt_hook_registers_running_and_final_without_provider_call(self):
        import os
        from src.sigma_fmea.execution_metadata import write_receipt
        source=receipt(self.root); record=json.loads(source.read_text()); record['status']='running'; record['row_count']=None
        with patch.dict(os.environ,{'SIGMA_RESEARCH_DATABASE':str(self.root/'hook.sqlite')}),patch('analysis.research.platform.snapshot'):
            with source.open('w+',encoding='utf-8') as stream:
                write_receipt(source,record,(),stream=stream)
                record['status']='failed'; write_receipt(source,record,(),stream=stream)
        hooked=Registry(self.root/'hook.sqlite')
        try:
            self.assertEqual(hooked.db.execute('SELECT count(*) FROM generations').fetchone()[0],1)
            self.assertEqual(hooked.db.execute('SELECT state FROM generations').fetchone()[0],'GENERATION_FAILED')
        finally: hooked.close()


class FakeGitHub:
    def __init__(self,payload,rate=False): self.payload=payload; self.rate=rate
    def get(self,path,binary=False):
        if self.rate: raise RateLimited('60')
        if binary: return self.payload
        return workflow()
    def pages(self,path,key):
        if self.rate: raise RateLimited('60')
        if key=='workflow_runs': return iter([workflow()])
        if key=='jobs': return iter([{'id':123}])
        return iter([{'id':9,'name':'fmea-results-1-1','expired':False}])


class SyncAndFinanceTests(unittest.TestCase):
    def test_sync_missing_artifacts_and_rate_limit_offline(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); store=Registry(root/'registry.sqlite')
            try:
                content=receipt(root).read_bytes(); buffer=io.BytesIO()
                with zipfile.ZipFile(buffer,'w') as archive:
                    archive.writestr('nested/a_execution.json',content)
                    archive.writestr('reference.xlsx',b'NEVER_READ')
                client=FakeGitHub(buffer.getvalue())
                state=synchronize(store,'test/repo',client)
                self.assertEqual(state['status'],'SUCCESS')
                self.assertEqual(store.reconcile()['generations'],1)
                state=synchronize(store,'test/repo',client)
                self.assertEqual(store.reconcile()['generations'],1)
                previous=state['last_successful_sync']; limited=synchronize(store,'test/repo',FakeGitHub(b'',True))
                self.assertEqual(limited['status'],'RATE_LIMITED'); self.assertEqual(limited['last_successful_sync'],previous)
                broken=FakeGitHub(b'notzip'); store.db.execute('DELETE FROM artifacts'); store.db.execute('DELETE FROM sync_runs'); state=synchronize(store,'test/repo',broken)
                self.assertEqual(state['status'],'PARTIAL'); self.assertTrue(store.reconcile()['missing_artifacts'])
            finally: store.close()

    def test_finance_missing_bills_reproducible_loss_and_assumption_changes(self):
        baseline=empty_snapshot()['baseline']; a=model([],[],baseline); b=model([],[],baseline)
        self.assertEqual(a,b); self.assertIsNone(a['measured']['actual_api_spending'])
        self.assertIsNone(a['measured']['verified_savings'])
        unknown=model([{'generation_status':'success','actual_cost':None,'generation_timestamp':'2026-11-15T10:00:00+00:00'}],[],baseline)
        self.assertIsNone(unknown['observed_spending'][0]['known_billed_subtotal'])
        costly={**DEFAULTS,'missed_reconstruction_minutes':300}
        loss=model([],[],baseline,costly)
        self.assertLess(loss['modeled']['first_year_net_savings'],0)
        self.assertIsNone(loss['modeled']['break_even_fmeas'])
        self.assertEqual(a,model([],[],baseline,dict(DEFAULTS)))
        measured=model([{'generation_status':'success','actual_cost':2}],[],baseline)
        self.assertEqual(measured['measured']['actual_api_spending'],2)
        self.assertEqual(measured['measured']['api_cost_per_success'],2)

if __name__=='__main__': unittest.main()
