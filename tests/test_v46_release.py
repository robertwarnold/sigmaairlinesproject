"""Offline official V4.0 run, receipt, registry and identifier-only judging."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import fmea_generator as engine
from analysis.engineering.judge_links import attach_judge_links
from analysis.engineering.store import EngineeringStore
from analysis.research.__main__ import empty_snapshot
from analysis.research.finance import model, review_volume_sensitivity
from analysis.research.github_sync import archive_generated_members, import_engineering_run
from analysis.research.platform import snapshot
from analysis.research.registry import Registry
from test_v4 import import_data, release_fixture


class ReleasePipelineTests(unittest.TestCase):
    def test_unversioned_provider_response_retains_failed_receipt_without_csv(self):
        with tempfile.TemporaryDirectory(dir='results') as directory:
            root=Path(directory)
            source=root/'input.txt'
            source.write_text('Synthetic input',encoding='utf-8')
            inventory,response=release_fixture()
            inventory['system_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            inventory_path=root/'input_inventory.json'
            inventory_path.write_text(json.dumps(inventory),encoding='utf-8')
            del response['schema_version']
            result={'text':json.dumps(response),'finish_reason':'STOP','max_output_tokens':10000}
            with (patch('fmea_generator.call_gemini',return_value=result) as call,
                  patch('fmea_generator.automatic_report'),patch('analysis.research.__main__.register')):
                with self.assertRaisesRegex(ValueError,'schema identifier'):
                    engine.generate_fmea(source,'system_A',version='v4.0',inventory_file=inventory_path,output_dir=root)
            call.assert_called_once()
            receipt=json.loads(next(root.glob('*_execution.json')).read_text(encoding='utf-8'))
            self.assertEqual(receipt['failure_classification'],'validation_failure')
            self.assertIn(next(root.glob('*_diagnostics.json')).name,receipt['artifacts'])
            self.assertFalse(list(root.glob('*.csv')))

    def test_artifact_registry_judge_and_adjudication(self):
        with tempfile.TemporaryDirectory(dir='results') as directory:
            root=Path(directory)
            package=root/'synthetic-input.txt'
            package.write_text('Synthetic component scenario only',encoding='utf-8')
            inventory, response=release_fixture()
            inventory['system_sha256']=hashlib.sha256(package.read_bytes()).hexdigest()
            inv=root/'input_inventory.json'
            inv.write_text(json.dumps(inventory),encoding='utf-8')
            result={'text':json.dumps(response),'finish_reason':'STOP','max_output_tokens':10000}
            with (patch('fmea_generator.call_gemini',return_value=result) as call,
                  patch('fmea_generator.automatic_report'), patch('analysis.research.__main__.register')):
                engine.generate_fmea(package,'system_A',version='v4.0',inventory_file=inv,
                                     output_dir=root,model='synthetic-only')
            call.assert_called_once()
            receipt_path=next(root.glob('*_execution.json'))
            receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
            zip_path=root/'synthetic.zip'
            with zipfile.ZipFile(zip_path,'w') as archive:
                for name in (*receipt['artifacts'],inv.name):
                    archive.write(root/name,name)
            registry=Registry(root/'registry.sqlite')
            workspace=EngineeringStore(root/'workspace.sqlite')
            try:
                gid=registry.receipt(receipt_path)
                with zipfile.ZipFile(zip_path) as archive:
                    members=archive_generated_members(registry,archive,receipt_path.name,receipt,gid)
                    self.assertTrue(any(item['member'].endswith('_diagnostics.json') for item in members))
                    self.assertTrue(import_engineering_run(registry,workspace,archive,receipt_path,receipt,members))
                judge=import_data()
                run=judge['runs'][0]
                run.update(run_id=gid,generated_rows=6,extra_unmatched_rows=5)
                row_id=response['rows'][0]['row_id']
                run['items'][0]['matched_row_id']=row_id
                judge_path=root/'judge.json'
                judge_path.write_text(json.dumps(judge),encoding='utf-8')
                registry.accept(judge,judge_path)
                projected=attach_judge_links(workspace.snapshot(),registry.path)
                record=next(row for row in projected['records'] if row['row_id']==row_id)
                self.assertEqual(record['judge_matches'][0]['judge_version'],'v1.2')
                workspace.review(record['record_id'],record['revision'],'NEEDS_REVIEW','Synthetic reviewer',
                                 'Potential additional failure needs evidence',{'judge_disposition':'insufficient_evidence'})
                self.assertEqual(len(next(row for row in workspace.records() if row['row_id']==row_id)['history']),4)
                public=snapshot(registry,root/'current.json',render=False)
                self.assertEqual(public['registry'][0]['diagnostics_summary']['candidate_rows'],6)
                self.assertNotIn('PRIVATE_SENTINEL',json.dumps(public))
                self.assertNotIn('Synthetic input only',json.dumps(public))
            finally:
                workspace.close()
                registry.close()

    def test_sensitivity_reconciles_selected_case_and_losses(self):
        baseline=empty_snapshot()['baseline']
        result=model([],[],baseline)
        grid=review_volume_sensitivity(result)
        volume=result['assumptions']['annual_volume']
        hours=sum(row['hours_per_fmea'] for row in result['activities']
                  if row['activity'] in ('Matched-item review','Missed-item reconstruction','Extra-row review'))
        center=next(row for row in grid if row['annual_volume']==volume and row['review_hours']==hours)
        self.assertAlmostEqual(center['first_year_net'],result['modeled']['first_year_net_savings'])
        self.assertEqual(center['break_even_volume'],result['modeled']['break_even_fmeas'])
        self.assertLess(min(row['first_year_net'] for row in grid),0)
        self.assertGreater(max(row['first_year_net'] for row in grid),0)
