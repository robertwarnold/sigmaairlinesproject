"""Synthetic standalone v3/round2 regressions; no reference FMEAs."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fmea_generator as engine
from standalone_v3 import CATEGORIES
from analysis.round2.__main__ import aggregate, ingest, metrics, plan, summarize, merge, comparison


def response():
    rows=[]; inventory=[]
    for uid,kind in [('motor1','component'),('motor2','component'),('wire','connection')]:
        ids=[]
        for direction in ('fail-open','fail-closed'):
            rid=uid+direction; ids.append(rid)
            rows.append({**{f:'synthetic' for f in engine.FIELDS},**{f:2 for f in engine.RATINGS},'component':uid,'failure_mode':direction,'row_id':rid,'unit_id':uid})
        inventory.append({'unit_id':uid,'name':uid,'kind':kind,'evidence':'synthetic input','relationships':[],
                          'cases':[{'category':c,'applicable':c in ('fail-open','fail-closed'),'rationale':'synthetic applicability','row_ids':[uid+c] if c in ('fail-open','fail-closed') else []} for c in CATEGORIES]})
    return {'inventory':inventory,'rows':rows,'review_flags':['synthetic only'],'complete':True}


def imported():
    return {'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':[{'run_id':'synthetic-1','system':'A','skill_version':'v2.0','generator_model':'synthetic','settings':{'temperature':0},'judge_model':'Claude Sonnet 5.5','judge_skill_version':'v1.2','ground_truth_version':'synthetic-only','classification_rules_version':'round1-human-reviewed','status':'validated','generated_rows':2,'extra_unmatched_rows':1,'items':[{'item_id':'x','found':True,'matched_row_id':'row1'},{'item_id':'y','found':False,'miss_category':'Repeated unit skipped'}]}]}


class Round2Tests(unittest.TestCase):
    def test_v2_selection_and_v3_schema(self):
        self.assertEqual(engine.PROMPT_VERSION,'v2.0')
        self.assertEqual(engine.SKILL_FILES['v2.0'].name,'fmea_instructions.md')
        from google.genai import types
        self.assertEqual(types.Schema.model_validate(engine.v3_schema()).type,types.Type.OBJECT)

    def test_inventory_directions_and_connection(self):
        rows,report=engine.parse_v3(json.dumps(response()))
        self.assertEqual(len(rows),6); self.assertEqual(report['identified_unit_count'],3)
        self.assertEqual(report['candidate_failure_cases_considered'],39)

    def test_incomplete_duplicate_missing_unit_and_direction(self):
        for mutation in ('complete','duplicate','missing_unit','direction','interface','truncated'):
            data=response()
            if mutation=='complete': data['complete']=False
            if mutation=='duplicate': data['rows'].append(data['rows'][0])
            if mutation in ('missing_unit','interface'): data['rows']=[r for r in data['rows'] if r['unit_id']!=('wire' if mutation=='interface' else 'motor2')]
            if mutation=='direction': data['inventory'][0]['cases'].pop()
            raw=json.dumps(data)
            if mutation=='truncated': raw=raw[:-5]
            with self.subTest(mutation=mutation),self.assertRaises((ValueError,KeyError)): engine.parse_v3(raw)

    def test_v3_generation_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'input.txt'; source.write_text('synthetic motors and wire')
            with patch('fmea_generator.call_gemini',return_value={'text':json.dumps(response()),'finish_reason':'STOP','max_output_tokens':10000}) as call,patch('fmea_generator.automatic_report'):
                engine.generate_fmea(source,'synthetic',version='v3.0-audit',output_dir=root)
            self.assertEqual(call.call_args.kwargs['version'],'v3.0-audit')
            receipt=json.loads((root/'synthetic_v3.0-audit_run01_execution.json').read_text())
            self.assertEqual(receipt['prompt_version'],'v3.0-audit'); self.assertEqual(receipt['completeness']['identified_unit_count'],3)

    def test_metrics_and_grouping(self):
        self.assertEqual(metrics([{'found':True},{'found':False}])['dpmo'],500000)
        rows=[{'skill_version':v,'system':s,'ground_truth_count':2,'missed':1,'missed_percentage':50,'extra_unmatched_rows':0} for v in ('v2.0','v3.0') for s in 'AB']
        self.assertEqual(len(summarize(rows,['skill_version','system'])),4)
        self.assertEqual(len(summarize(rows,['skill_version'])),2)
        with self.assertRaises(ValueError): metrics([])

    def test_import_idempotency_duplicates_missing_and_privacy(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); path=root/'judge.json'; data=imported(); path.write_text(json.dumps(data))
            first=aggregate([path],root/'analysis'); second=aggregate([path,path],root/'analysis')
            self.assertEqual(first,second); self.assertEqual(first['item_count'],2); self.assertTrue(first['missing_data'])
            data['runs'].append(copy.deepcopy(data['runs'][0])); path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Duplicate'): ingest([path])
            data=imported(); data['runs'][0]['items'][0]['ground_truth_text']='forbidden'; path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'confidential'): ingest([path])
        with self.assertRaises(ValueError): ingest([Path('reference_materials/anything.json')])

    def test_merge_batches_and_reject_conflicts(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); paths=[]
            for n in range(2):
                data=response()
                for unit in data['inventory']:
                    unit['unit_id']=str(n)+unit['unit_id']
                    for case in unit['cases']: case['row_ids']=[str(n)+r for r in case['row_ids']]
                for row in data['rows']:
                    for key in ('unit_id','row_id','component'): row[key]=str(n)+row[key]
                path=root/f'batch{n}.json'; path.write_text(json.dumps(data)); paths.append(path)
            rows,report=merge(paths,root/'merged.json')
            self.assertEqual(len(rows),12); self.assertEqual(report['identified_unit_count'],6)
            with self.assertRaises(ValueError): merge([paths[0],paths[0]],root/'bad.json')

    def test_incompatible_conditions_and_summary_not_trusted(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            path=Path(temp)/'import.json'; data=imported()
            data['runs'][0]['missed']=0
            path.write_text(json.dumps(data))
            self.assertEqual(ingest([path])[0][0]['missed'],1)
            other=copy.deepcopy(data['runs'][0]); other['run_id']='different'; other['settings']={'temperature':1}
            data['runs'].append(other); path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,'Incompatible'): ingest([path])

    def test_receipt_join(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); data=imported(); receipt=root/'execution.json'
            receipt.write_text(json.dumps({'workflow':'standalone_gemini','status':'success','prompt_version':'v2.0','model':'synthetic','system_id':'system_A','row_count':2,'api_request_seconds':12,'usage_metadata':{'tokens':5}}))
            data['runs'][0]['generation_receipt_path']=str(receipt)
            path=root/'judge.json'; path.write_text(json.dumps(data))
            self.assertEqual(ingest([path])[0][0]['generation_seconds'],12)
            obj=json.loads(receipt.read_text()); obj['status']='failed'; receipt.write_text(json.dumps(obj))
            with self.assertRaisesRegex(ValueError,'receipt'): ingest([path])

    def test_anova_waits_and_computes_additive_version_effect(self):
        self.assertNotIn('anova',comparison([],[],[]))
        runs=[]
        for v in ('v2.0','v3.0'):
            for s in 'ABCDE':
                for r in range(4):
                    pct=30+ord(s)-65+r if v=='v2.0' else 10+ord(s)-65+r
                    runs.append({'skill_version':v,'system':s,'ground_truth_count':100,'missed':pct,'missed_percentage':pct,'extra_unmatched_rows':2})
        result=comparison(runs,summarize(runs,['skill_version','system']),summarize(runs,['skill_version']))
        self.assertLess(result['anova']['p'],.05)
        self.assertTrue(all(result['criteria'].values()))

    def test_plan_reproducible_and_exclusive(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp)
            a=plan(root/'a','unconfirmed-model'); b=plan(root/'b','unconfirmed-model')
            self.assertEqual(a,b); self.assertEqual(len(a['runs']),20)
            self.assertEqual(len({r['run_id'] for r in a['runs']}),20)
            with self.assertRaises(FileExistsError): plan(root/'a','unconfirmed-model')

if __name__=='__main__': unittest.main()
