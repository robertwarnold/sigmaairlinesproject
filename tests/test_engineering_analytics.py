"""Synthetic fixtures only; no reference worksheets or fabricated study observations."""
import copy
import tempfile
from pathlib import Path
import unittest
from tests.test_engineering_workspace import fixture
from analysis.engineering.store import EngineeringStore
from analysis.engineering.analytics import selected_analytics, operational_activity


class AnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory(dir='results'))
        self.root=Path(self.temp); self.store=EngineeringStore(self.root/'store.sqlite'); self.addCleanup(self.store.close)
        self.store.ingest(*fixture(self.root/'inputs'),'synthetic-v1')

    def test_selected_metrics_use_valid_ratings_and_citation_presence(self):
        s=self.store.snapshot(); a=selected_analytics(s,[s['rows'][0]['record_id']])
        self.assertEqual(a['kpis']['total'],1); self.assertEqual(a['kpis']['high_severity'],1)
        self.assertEqual(a['kpis']['average_rpn'],9); self.assertEqual(a['kpis']['cited_evidence_percentage'],100)
        self.assertEqual(a['evidence'][0]['status'],'Pending verification')
        self.assertEqual(a['cause_categories'],[{'category':'Not categorized','count':1}])
        self.assertEqual(a['actions'],[]); self.assertIsNone(a['agreement'][0]['within_one_percentage'])
        self.assertEqual(a['runs'][0]['selected_rows'],1)
        self.assertEqual(a['subsystems'][0]['width_percentage'],100)
        self.assertIsNone(a['runs'][0]['acceptance_percentage'])

    def test_empty_selection_is_not_zero_quality(self):
        a=selected_analytics(self.store.snapshot(),[])
        self.assertEqual(a['kpis']['total'],0)
        for key in ('average_rpn','cited_evidence_percentage','validation_percentage'): self.assertIsNone(a['kpis'][key])
        self.assertEqual(a['runs'],[])

    def test_unknown_and_duplicate_selection_rejected(self):
        s=self.store.snapshot(); rid=s['rows'][0]['record_id']
        for ids in ([rid,rid],['unknown']):
            with self.assertRaises(ValueError): selected_analytics(s,ids)

    def test_review_rating_agreement_requires_actual_correction_and_pairs(self):
        s=self.store.snapshot();r=s['records'][0]
        self.store.review(r['record_id'],r['revision'],'APPROVED','Synthetic engineer','Explicit synthetic correction',{'severity':8},'approved_inference',True)
        s=self.store.snapshot();a=selected_analytics(s,[r['record_id']])
        self.assertEqual(a['agreement'][0]['n'],1); self.assertIsNone(a['agreement'][0]['within_one_percentage'])
        self.assertEqual(a['agreement'][1]['n'],0)
        second=copy.deepcopy(s['records'][0]);second['record_id']='synthetic-second';second['row_id']='r2'
        s['records'].append(second)
        a=selected_analytics(s,[r['record_id'],'synthetic-second'])
        self.assertEqual(a['agreement'][0]['within_one_percentage'],100)
        self.assertEqual(a['kpis']['average_rpn'],8)

    def test_missing_rpn_excluded_and_duplicate_rates_within_runs(self):
        s=self.store.snapshot();r=s['records'][0]; r['current']['severity']=None
        a=selected_analytics(s,[r['record_id']]); self.assertIsNone(a['kpis']['average_rpn'])
        self.assertEqual(a['kpis']['valid_rpn_count'],0)
        r2=copy.deepcopy(r);r2['record_id']='second';s['records'].append(r2)
        a=selected_analytics(s,[r['record_id'],'second']);self.assertEqual(a['runs'][0]['duplicate_percentage'],50)
        r2['run_id']='independent-replicate'
        a=selected_analytics(s,[r['record_id'],'second']);self.assertTrue(all(x['duplicate_percentage']==0 for x in a['runs']))

    def test_operational_receipt_deduplication_and_failures(self):
        rows=[{'generation_id':'one','generation_timestamp':'2026-11-15','generation_status':'success','evaluation_status':'awaiting_evaluation'},
              {'generation_id':'two','generation_timestamp':'2026-11-15','generation_status':'failed'}]
        a=operational_activity(rows+[rows[0]])
        self.assertEqual(a['registered_generations'],2);self.assertEqual(a['awaiting_judge'],1)
        self.assertEqual(sum(x['count'] for x in a['generation_activity']),2)
        with self.assertRaises(ValueError):operational_activity(rows+[{**rows[0],'generation_status':'failed'}])
