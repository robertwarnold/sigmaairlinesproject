"""Synthetic offline telemetry, reconciliation, rendering and publication regressions."""
import copy
import csv
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

import fmea_generator as engine
from analysis.experiments import catalog, report, figures
from analysis.financial_impact.data_schema import read_json
from analysis.financial_impact.ingest import import_attempts, sha256
from analysis.financial_impact.report import CONFIG
from src.sigma_fmea import execution_metadata as telemetry


class ExperimentMetricsTests(unittest.TestCase):
    """Use fabricated engineering rows only; never contact a model or read research worksheets."""

    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.assumptions=read_json(CONFIG/'assumptions.json')

    def receipt(self,system='system_C',attempt='one',campaign='synthetic',status='success',usage=True):
        """Build a hash-bound synthetic receipt and valid one-row worksheet if successful."""
        folder=self.root/campaign/attempt;folder.mkdir(parents=True)
        raw={'metadata_schema':'fmea-execution-1','experiment_id':campaign,'attempt_id':attempt,
            'system_id':system,'prompt_version':'v2.0','model':'gemini-3.8-flash',
            'skill_sha256':'b'*64,'system_sha256':'a'*64,'workflow':'standalone_gemini',
            'started_at':'2026-11-01T00:00:00Z','finished_at':'2026-11-01T00:00:02Z',
            'status':status,'total_elapsed_seconds':2,'api_request_seconds':1.5,
            'parsing_validation_seconds':.1,'configuration':{'temperature':0,'retry_attempts':1},
            'usage_metadata':{'prompt_token_count':100,'candidates_token_count':50,'thoughts_token_count':20} if usage else None}
        artifacts=[]
        if status=='success':
            csv_path=folder/'draft.csv'
            row={field:'synthetic example' for field in engine.FIELDS}
            row.update(severity=2,occurrence=3,detection=4,RPN=24,case_id=system,version='v2.0',run=1,model=raw['model'])
            with csv_path.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=engine.CSV_FIELDS);writer.writeheader();writer.writerow(row)
            artifacts=[csv_path]
        path=folder/(attempt+'_execution.json');telemetry.write_receipt(path,raw,artifacts)
        return path

    def ingest(self,paths,cached=False):
        """Resolve synthetic artifacts inside the temporary fixture directory only."""
        return catalog.ingest(paths,[self.root],self.root/'catalog.json' if cached else None)[0]

    def test_success_usage_provisional_and_unknown_actual_billing(self):
        entries=self.ingest([self.receipt()]);entry=entries[0]
        self.assertEqual(entry['metrics']['row_count'],1)
        self.assertIsNone(entry['metrics']['component_coverage'])
        self.assertEqual(entry['receipt']['engineering_review_status'],'unreviewed')
        rows=catalog.financial_rows(entries,self.assumptions)
        self.assertGreater(rows[0]['cost_usd'],0)
        self.assertNotEqual(rows[0]['cost_basis'],'invoice')

    def test_partial_recovery_and_retry_history(self):
        failure=self.receipt(attempt='failed',status='failed',usage=False)
        raw=read_json(failure);raw.update(http_status=503,provider_error_classification='provider_unavailable_503',retry_wait_seconds=60)
        failure.write_text(json.dumps(raw))
        success=self.receipt(attempt='retry');raw=read_json(success);raw.update(retry_number=1,supersedes_attempt_id='failed');success.write_text(json.dumps(raw))
        unresolved=self.receipt(system='system_E',attempt='unresolved',status='failed',usage=False)
        entries=catalog.select(self.ingest([failure,success,unresolved]))
        self.assertEqual(len(entries),3)
        self.assertEqual(sum(e['primary'] for e in entries),1)
        self.assertEqual(sum(figures.outcome(e)=='provider' for e in entries),1)
        rows=catalog.financial_rows(entries,self.assumptions)
        self.assertIsNone(next(r for r in rows if r['attempt_id']=='failed')['cost_usd'])
        self.assertEqual(sum(r['retry_wait_seconds'] for r in rows),60)

    def test_duplicate_ingestion_is_idempotent(self):
        path=self.receipt();first=self.ingest([path,path],True);second=self.ingest([path],True)
        self.assertEqual(first,second);self.assertEqual(len(second),1)

    def test_conflicting_logical_duplicate_rejected(self):
        path=self.receipt();self.ingest([path],True)
        raw=read_json(path);raw['total_elapsed_seconds']=3;path.write_text(json.dumps(raw))
        with self.assertRaisesRegex(ValueError,'Duplicate logical'):self.ingest([path],True)

    def test_conflicting_physical_status_rejected(self):
        entry=self.ingest([self.receipt()])[0];other=copy.deepcopy(entry);other['receipt']['status']='failed'
        with self.assertRaisesRegex(ValueError,'status'):catalog.merge(entry,other)

    def test_multiple_campaigns_same_attempt_prefix(self):
        entries=self.ingest([self.receipt(campaign='first'),self.receipt(campaign='second')])
        rows=catalog.financial_rows(entries,self.assumptions)
        self.assertEqual({r['experiment_id'] for r in rows},{'first','second'})

    def test_reconciliation_embedded_receipts_deduplicate(self):
        path=self.receipt();manifest=self.root/'reconciliation_manifest.json'
        manifest.write_text(json.dumps({'financial_schema':'reconciled-campaign-1','attempts':[read_json(path)]}))
        self.assertEqual(len(self.ingest([path,manifest])),1)

    def test_invalid_rpn_and_wrong_system_excluded(self):
        path=self.receipt();csv_path=path.parent/'draft.csv'
        for before,after in (('24','25'),('system_C','system_E')):
            with self.subTest(after=after):
                original=csv_path.read_text();csv_path.write_text(original.replace(before,after))
                raw=read_json(path);raw['artifacts']['draft.csv']['sha256']=sha256(csv_path);path.write_text(json.dumps(raw))
                self.assertFalse(self.ingest([path])[0]['metrics']['schema_valid'])
                csv_path.write_text(original)

    def test_changed_cached_artifact_invalidates_observation(self):
        path=self.receipt();self.ingest([path],True);(path.parent/'draft.csv').write_text('changed')
        self.assertFalse(self.ingest([],True)[0]['metrics']['schema_valid'])

    def test_legacy_observation_date_is_not_generation_start(self):
        path=self.receipt();raw=read_json(path);raw.update(started_at=None,observed_at='2026-11-01T00:00:00Z',duration_kind='legacy_recorded_generation_minutes',usage_metadata=None)
        path.write_text(json.dumps(raw));row=catalog.financial_rows(self.ingest([path]),self.assumptions)[0]
        self.assertIsNone(row['started_at']);self.assertEqual(row['timestamp_basis'],'recorded_observation_date_only')
        self.assertIsNone(row['cost_usd'])

    def test_canonical_and_frozen_sources_excluded(self):
        path=self.receipt();raw=read_json(path);raw['workflow']='canonical_research:condition';path.write_text(json.dumps(raw))
        self.assertEqual(self.ingest([path]),[])
        with self.assertRaises(ValueError):catalog.discover([self.root/'research_results'])

    def test_verified_http_only_and_no_string_503(self):
        from google.genai.errors import ServerError
        self.assertIsNone(telemetry.failure_metadata(RuntimeError('HTTP 503'))['http_status'])
        self.assertEqual(telemetry.failure_metadata(ServerError(503,{'error':{'message':'synthetic'}}))['provider_error_classification'],'provider_unavailable_503')

    def test_reporting_failure_preserves_generation_outcome(self):
        path=self.receipt();before=path.read_bytes()
        with patch.dict(os.environ,{'SIGMA_FMEA_AUTOREPORT':'on','GITHUB_ACTIONS':'false'}), patch('analysis.experiments.report.post_generation',side_effect=RuntimeError('synthetic')):
            status=telemetry.automatic_report(path)
        self.assertEqual(status['status'],'failed');self.assertEqual(path.read_bytes(),before)
        self.assertTrue(status['generation_outcome_unchanged'])

    def test_actions_defers_to_offline_job(self):
        path=self.receipt()
        with patch.dict(os.environ,{'SIGMA_FMEA_AUTOREPORT':'on','GITHUB_ACTIONS':'true'}),patch('analysis.experiments.report.post_generation') as run:
            self.assertEqual(telemetry.automatic_report(path)['status'],'deferred_to_offline_actions_job')
        run.assert_not_called()

    def test_reconciled_selection_never_promotes_failed_output(self):
        path=self.receipt(status='failed');index=self.root/'index.json'
        index.write_text(json.dumps({'systems':[{'system_id':'system_C','source_campaign':'synthetic','effective_attempt_id':'one'}]}))
        with self.assertRaisesRegex(ValueError,'missing or no longer validates'):catalog.select(self.ingest([path]),index)

    def test_acceptance_requires_condition_matched_independent_review(self):
        entries=self.ingest([self.receipt()]);financial=catalog.financial_rows(entries,self.assumptions)
        review={**financial[0],'method':'ai_assisted','case_id':'one','decision':'accepted','independent_review':'false'}
        report.attach_reviews(entries,financial,[review]);self.assertEqual(entries[0]['review_status'],'unreviewed')
        review['independent_review']='true'
        report.attach_reviews(entries,financial,[review]);self.assertEqual(entries[0]['review_status'],'accepted')
        review['input_hash']='different'
        report.attach_reviews(entries,financial,[review]);self.assertEqual(entries[0]['review_status'],'unreviewed')

    def test_full_offline_render_financial_execution_and_publication(self):
        paths=[self.receipt(),self.receipt(system='system_E',attempt='failed',status='failed',usage=False)]
        # Any accidental provider path fails before a request; the financial subprocess has no provider keys.
        with patch.object(socket,'create_connection',side_effect=AssertionError('offline only')),patch('fmea_generator.call_gemini',side_effect=AssertionError('no generation')):
            output=report.create_report(paths,[self.root],self.root/'reports',analysis_id='synthetic-v1')
        manifest=read_json(output/'dashboard_manifest.json')
        self.assertEqual(manifest['data_audit']['unique_attempts'],2)
        self.assertEqual(len(list((output/'figures').glob('*.png'))),10)
        self.assertEqual(read_json(output/'financial/financial-v1/metrics.json')['observed']['n_attempts'],2)
        self.assertIn('DATA AUDIT',(output/'financial_execution.log').read_text())
        self.assertEqual(manifest['data_audit']['independent_acceptance_decisions'],0)
        before=sha256(output/'dashboard_manifest.json')
        with self.assertRaises(FileExistsError):report.create_report(paths,[self.root],self.root/'reports',analysis_id='synthetic-v1')
        self.assertEqual(sha256(output/'dashboard_manifest.json'),before)
        staged=report.publish_stage(output,self.root/'publication')
        self.assertFalse(list(staged.rglob('*.csv')))
        self.assertEqual(read_json(staged/'publication_manifest.json')['approval_status'],'pending_human_review')

    def test_empty_dataset_rendering(self):
        captions=figures.render([],[],self.root/'empty-figures')
        self.assertEqual(len(captions),10)

    def test_local_generator_reports_success_and_failure_without_extra_requests(self):
        system=self.root/'input.txt';system.write_text('synthetic input')
        row={field:'synthetic example' for field in engine.FIELDS};row.update(severity=2,occurrence=3,detection=4)
        for number,outcome in enumerate(({'text':json.dumps([row]),'finish_reason':'STOP','max_output_tokens':100},RuntimeError('synthetic transport')),1):
            with self.subTest(number=number),patch('fmea_generator.call_gemini',side_effect=outcome if isinstance(outcome,Exception) else None,return_value=outcome) as call,patch('fmea_generator.automatic_report') as automatic:
                if isinstance(outcome,Exception):
                    with self.assertRaises(RuntimeError):engine.generate_fmea(system,'synthetic',output_dir=self.root/str(number))
                else:engine.generate_fmea(system,'synthetic',output_dir=self.root/str(number))
                call.assert_called_once();automatic.assert_called_once()
                recorded=read_json(automatic.call_args.args[0])
                self.assertEqual(recorded['status'],'failed' if isinstance(outcome,Exception) else 'success')

    def test_explicit_synthetic_scenario_uses_existing_model(self):
        from analysis.financial_impact.report import create_report
        path=self.receipt();scenario=read_json(CONFIG/'templates/scenario_template.json')
        values={'labor_rate':100,'manual_hours':10,'ai_hours':2,'api_usd_per_attempt':.1,'success_probability':.8,'maintenance_usd':20,'development_usd':100,'annual_volume':50}
        scenario.update(rationale='Synthetic testing only; never observed savings',approval_status='synthetic_fixture')
        for key,value in values.items():scenario['distributions'][key]['value']=value
        scenario_path=self.root/'scenario.json';scenario_path.write_text(json.dumps(scenario))
        output,_=create_report([path],output_root=self.root/'financial',analysis_id='synthetic-scenario',scenario_path=scenario_path)
        metrics=read_json(output/'metrics.json')
        self.assertEqual(metrics['simulation']['status'],'scenario')
        self.assertEqual(metrics['matched_case_count_including_estimated_pairs'],0)
        self.assertTrue(list((output/'figures').glob('14_*.png')))


if __name__=='__main__':unittest.main()
