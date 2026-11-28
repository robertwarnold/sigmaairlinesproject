"""Synthetic generated-output fixtures only. No engineer reference worksheets."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from analysis.engineering.store import EngineeringStore, compare_keys, encoded, export_csv, file_digest, findings, rpn, validate_workspace
from standalone_v4 import CATEGORIES
from fmea_generator import FIELDS


def fixture(root, attempt='run-1'):
    root.mkdir(parents=True,exist_ok=True)
    unit={'unit_id':'u1','name':'Synthetic motor','kind':'component','parent_id':None,'relationships':[],
          'function':'Synthetic rotation','evidence':'Synthetic input only','detection_provisions':'Not provided',
          'operating_states':['operating'],'applicable_categories':['failure to start']}
    inv={'schema':'input-inventory-4','system_sha256':'synthetic-input-hash','units':[unit],'review_flags':[],'review_status':'reviewed'}
    row={**{k:'Synthetic '+k for k in FIELDS},'severity':9,'occurrence':1,'detection':1,'component':unit['name'],
         'row_id':'r1','unit_id':'u1','category':'failure to start','operating_state':'operating',
         'existing_detection':'Not provided','assumptions':'Synthetic assumptions','source_criticality':'SOURCE-CLASS-PRESERVED'}
    raw={'rows':[row],'cases':[{'unit_id':'u1','category':c,'applicable':c=='failure to start','rationale':'Synthetic applicability',
                               'row_ids':['r1'] if c=='failure to start' else []} for c in CATEGORIES],'review_flags':[],'complete':True}
    response=root/'response.json'; inventory=root/'inventory.json'; receipt=root/'receipt.json'
    response.write_text(encoded(raw),encoding='utf-8'); inventory.write_text(encoded(inv),encoding='utf-8')
    meta={'workflow':'standalone_gemini','prompt_version':'v4.0-inventory','attempt_id':attempt,'experiment_id':'SYNTHETIC-ONLY',
          'system_id':'A','system_sha256':inv['system_sha256'],'inventory_sha256':file_digest(inventory),'skill_sha256':'synthetic-skill',
          'model':'synthetic-offline','configuration':{'temperature':0},'git_commit':'synthetic','started_at':'2026-11-15T00:00:00+00:00',
          'status':'success','artifacts':{'response.json':{'sha256':file_digest(response)}},'data_origin':'synthetic_test'}
    receipt.write_text(encoded(meta),encoding='utf-8')
    return response,inventory,receipt


class EngineeringWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory(dir='results'))
        self.root=Path(self.temp); self.store=EngineeringStore(self.root/'engineering.sqlite'); self.addCleanup(self.store.close)
        self.paths=fixture(self.root/'inputs'); self.store.ingest(*self.paths,'synthetic-v1')

    def test_schema_adapter_idempotent_original_and_hash_binding(self):
        self.store.ingest(*self.paths,'synthetic-v1')
        snap=self.store.snapshot(); self.assertEqual(len(snap['rows']),1)
        self.assertEqual(snap['records'][0]['original']['source_criticality'],'SOURCE-CLASS-PRESERVED')
        self.assertEqual(snap['summary']['high_severity_rows'],1); self.assertEqual(snap['rows'][0]['RPN'],9)
        self.paths[0].write_text('{}',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'not bound'): self.store.ingest(*self.paths,'synthetic-v1')

    def test_missing_invalid_ratings_never_default(self):
        row=self.store.records()[0]['original']
        for value in (None,0,11,True,3.5,'3'):
            candidate={**row,'severity':value}; self.assertIsNone(rpn(candidate))
            self.assertEqual(findings(candidate,self.store.records()[0]['unit'])['structural_status'],'FAIL')

    def test_review_append_only_approval_reopen_and_concurrency(self):
        r=self.store.records()[0]; original=copy.deepcopy(r['original'])
        with self.assertRaisesRegex(ValueError,'confirmation'): self.store.review(r['record_id'],2,'APPROVED','Engineer','Synthetic review')
        self.store.review(r['record_id'],2,'APPROVED','Engineer','Synthetic engineering decision',{'occurrence':2},'approved_inference',True)
        new=self.store.records()[0]; self.assertEqual(new['original'],original); self.assertEqual(rpn(new['current']),18)
        with self.assertRaisesRegex(ValueError,'Stale'): self.store.review(r['record_id'],2,'REJECTED','Engineer','stale')
        with self.assertRaisesRegex(ValueError,'Reopen'): self.store.review(r['record_id'],3,'REJECTED','Engineer','change')
        self.store.review(r['record_id'],3,'NEEDS_REVIEW','Engineer','Reopen for reassessment')
        self.assertEqual(len(self.store.records()[0]['history']),5)

    def test_evidence_approval_and_correction_validation(self):
        r=self.store.records()[0]
        with self.assertRaisesRegex(ValueError,'citation'): self.store.review(r['record_id'],2,'APPROVED','Engineer','check',{'evidence':'Not provided'},'source_verified',True)
        with self.assertRaisesRegex(ValueError,'immutable'): self.store.review(r['record_id'],2,'NEEDS_REVIEW','Engineer','edit',{'RPN':1})
        with self.assertRaises(ValueError): self.store.review(r['record_id'],2,'NEEDS_REVIEW','Engineer','edit',{'severity':False})
        self.assertEqual(self.store.records()[0]['revision'],2)

    def test_export_formula_safety_and_private_path(self):
        r=self.store.records()[0]; self.store.review(r['record_id'],2,'NEEDS_REVIEW','Engineer','Synthetic correction',{'cause':'=SYNTHETIC()'})
        path=self.root/'rows.csv'; export_csv(self.store.snapshot(),path)
        self.assertIn("'=SYNTHETIC()",path.read_text(encoding='utf-8'))
        with self.assertRaises(ValueError): export_csv(self.store.snapshot(),Path('public-engineering.csv'))
        self.assertIn('original',self.store.snapshot()['records'][0])

    def test_incompatible_comparison_rejected_and_no_judge_scores(self):
        self.store.ingest(*fixture(self.root/'other','run-2'),'different-dataset-version')
        snap=self.store.snapshot()
        with self.assertRaisesRegex(ValueError,'Incompatible'): compare_keys(snap,[r['run_id'] for r in snap['comparisons']])
        self.assertIsNone(snap['comparisons'][0]['recall']); self.assertIsNone(snap['comparisons'][0]['precision'])

    def test_risk_metrics_are_row_counts_not_frequency_or_acceptance(self):
        snap=self.store.snapshot(); self.assertEqual(snap['risk']['original']['matrix'],[{'severity':9,'occurrence':1,'count':1}])
        self.assertEqual(snap['risk']['current']['rpn_bins'][0]['count'],1)
        self.assertEqual(snap['risk']['current']['actions'],[])
        self.assertEqual(snap['rows'][0]['review_status'],'NEEDS_REVIEW')

    def test_workflows_and_version_identity_are_separate(self):
        meta=json.loads(self.paths[2].read_text()); meta['workflow']='canonical'; self.paths[2].write_text(encoded(meta))
        with self.assertRaisesRegex(ValueError,'canonical'): self.store.ingest(*self.paths,'synthetic-v1')

    def test_duplicate_detection_is_within_run_and_input_unit(self):
        raw=json.loads(self.paths[0].read_text()); raw['rows'].append({**raw['rows'][0],'row_id':'r2'})
        self.paths[0].write_text(encoded(raw)); meta=json.loads(self.paths[2].read_text()); meta['attempt_id']='duplicates'
        meta['artifacts']['response.json']['sha256']=file_digest(self.paths[0]); self.paths[2].write_text(encoded(meta))
        self.store.ingest(*self.paths,'synthetic-v1'); snap=self.store.snapshot()
        compared=next(r for r in snap['comparisons'] if r['run_id'].endswith(':duplicates'))
        self.assertEqual(compared['duplicate_rows'],1)
        self.assertIn('Duplicate original fingerprint',str(snap['records']))

    def test_missing_ratings_can_be_repaired_without_changing_original(self):
        raw=json.loads(self.paths[0].read_text()); raw['rows'][0]['severity']=None
        self.paths[0].write_text(encoded(raw)); meta=json.loads(self.paths[2].read_text()); meta['attempt_id']='missing-rating'
        meta['artifacts']['response.json']['sha256']=file_digest(self.paths[0]); self.paths[2].write_text(encoded(meta))
        self.store.ingest(*self.paths,'synthetic-v1'); record=next(r for r in self.store.records() if r['run_id'].endswith('missing-rating'))
        self.assertIsNone(rpn(record['current']))
        with self.assertRaisesRegex(ValueError,'structural'): self.store.review(record['record_id'],2,'APPROVED','Engineer','Missing rating',None, 'approved_inference',True)
        self.store.review(record['record_id'],2,'APPROVED','Engineer','Synthetic reviewed rating',{'severity':8},'approved_inference',True)
        record=next(r for r in self.store.records() if r['record_id']==record['record_id'])
        self.assertIsNone(record['original']['severity']); self.assertEqual(rpn(record['current']),8)

    def test_actions_and_overdue_derive_only_from_recorded_status(self):
        record=self.store.records()[0]
        self.store.review(record['record_id'],2,'NEEDS_REVIEW','Engineer','Synthetic action',{'action_status':'OPEN','action_due_date':'2000-01-01','action_owner':'Synthetic engineer'})
        self.assertEqual(self.store.snapshot()['risk']['current']['actions'],[{'state':'OVERDUE','count':1}])
        with self.assertRaises(ValueError): self.store.review(record['record_id'],3,'NEEDS_REVIEW','Engineer','Bad due date',{'action_due_date':'not-a-date'})
        self.assertEqual(self.store.records()[0]['revision'],3)

    def test_source_binding_configuration_allowlist_and_filtered_export(self):
        meta=json.loads(self.paths[2].read_text()); meta['configuration']['api_key']='SYNTHETIC_SECRET_SENTINEL'; meta['attempt_id']='safe-config'
        self.paths[2].write_text(encoded(meta)); self.store.ingest(*self.paths,'synthetic-v1')
        snap=self.store.snapshot(); self.assertNotIn('SYNTHETIC_SECRET_SENTINEL',encoded(snap))
        self.assertTrue(snap['records'][0]['evidence_refs'])
        path=self.root/'selected.csv'; export_csv(snap,path,[snap['rows'][0]['record_id']])
        self.assertEqual(len(path.read_text().splitlines()),2)

    def test_snapshot_rejects_corrupt_metrics_and_identity(self):
        for mutate in (
            lambda s: s['rows'][0].update(RPN=999),
            lambda s: s['rows'][0].update(severity=True),
            lambda s: s.update(private=False),
            lambda s: s['records'][0]['original'].update(cause='changed'),
        ):
            snap=self.store.snapshot(); mutate(snap)
            with self.assertRaises(ValueError): validate_workspace(snap)

    def test_selected_json_export_preserves_original_and_scope(self):
        import subprocess
        import sys
        selection=self.root/'selection.json'; selection.write_text(encoded([self.store.records()[0]['record_id']]))
        output=self.root/'selected.json'
        command=[sys.executable,'-m','analysis.engineering','--database',str(self.root/'engineering.sqlite'),
                 'export','--format','json','--selection',str(selection),'--output',str(output)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        data=json.loads(output.read_text(encoding='utf-8'))
        self.assertEqual(data['schema'],'engineering-record-export-1')
        self.assertEqual(data['scope'],'selected_record_ids'); self.assertTrue(data['private'])
        self.assertEqual(len(data['rows']),1); self.assertEqual(data['records'][0]['original']['severity'],9)
        self.assertNotIn('summary',data)
        selection.write_text(encoded(['unknown-record']))
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(json.loads(output.read_text(encoding='utf-8')),data)
