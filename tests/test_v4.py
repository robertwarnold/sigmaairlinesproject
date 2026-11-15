"""Synthetic V4 engineering and research regression tests; no reference worksheets."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import fmea_generator as engine
from standalone_v4 import CATEGORIES, audit, load_inventory, validate, extract_inventory
from analysis.research.__main__ import empty_snapshot, validate_snapshot, build, atomic_json, register, review_events, plan, review_sample
from analysis.research.statistics import bootstrap, anova, compare
from analysis.round2.__main__ import ingest, metrics, summarize


def fixture():
    units=[]; rows=[]; cases=[]
    for i,kind in enumerate(('component','component','connection'),1):
        uid=f'u{i}'
        units.append({'unit_id':uid,'name':f'Synthetic unit {i}','kind':kind,'parent_id':None,'relationships':[],
                      'function':'transmit synthetic signal','operating_states':['operating'],
                      'evidence':'Synthetic input only','detection_provisions':'Not provided',
                      'repeat_group':'pair' if i<3 else 'wire','repeat_quantity':2 if i<3 else 1,
                      'repeat_index':i if i<3 else 1,'applicable_categories':['electrical open circuit','electrical short circuit']})
        for category in CATEGORIES:
            applicable=category in units[-1]['applicable_categories']; ids=[]
            if applicable:
                rid=uid+'-'+str(CATEGORIES.index(category)); ids=[rid]
                rows.append({**{f:'synthetic content' for f in engine.FIELDS},**{f:3 for f in engine.RATINGS},
                             'component':units[-1]['name'],'failure_mode':category,'cause':'synthetic mechanism','system_effect':'synthetic system loses signal',
                             'row_id':rid,'unit_id':uid,'category':category,'operating_state':'operating','existing_detection':'Not provided','assumptions':'synthetic test only'})
            cases.append({'unit_id':uid,'category':category,'applicable':applicable,'rationale':'synthetic applicability','row_ids':ids})
    return {'schema':'input-inventory-4','units':units,'review_flags':[],'review_status':'reviewed'}, {'rows':rows,'cases':cases,'review_flags':[],'complete':True}


def import_data(version='v4.0'):
    return {'schema':'standalone-judge-import-1','workflow':'standalone_gemini','runs':[{
        'data_origin':'synthetic_test','run_id':'synthetic-A-1','system':'A','skill_version':version,'generator_model':'synthetic-only',
        'settings':{'temperature':0},'judge_model':'Claude Sonnet 5.5','judge_skill_version':'v1.2',
        'ground_truth_version':'synthetic','classification_rules_version':'synthetic','status':'validated',
        'generated_rows':2,'extra_unmatched_rows':1,'items':[{'item_id':'opaque1','found':True,'matched_row_id':'g1','judge_notes':'PRIVATE_SENTINEL'},
                                                        {'item_id':'opaque2','found':False,'miss_category':'Part never covered'}]}]}


class V4EngineeringTests(unittest.TestCase):
    def test_version_identity_and_preservation(self):
        self.assertEqual(engine.PROMPT_VERSION,'v2.0')
        self.assertEqual(len(set(engine.SKILL_FILES.values())),4)
        self.assertEqual(hashlib.sha256(engine.SKILL_FILES['v2.0'].read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'082d9e51a01611a2daa7cecab7600359f8920ac64327b643e2fd4fe97942f7a3')
        self.assertEqual(hashlib.sha256(engine.SKILL_FILES['v3.0'].read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'d9877524017e949570f5b623b197b1c8db117d9d456cbab28f9756f22e45e3b2')
        self.assertEqual(hashlib.sha256(engine.SKILL_FILES['v3.0-audit'].read_bytes().replace(b'\r\n',b'\n')).hexdigest(),'a34f9fa40aa02603d36db25efe4b2aae45efa0f328b74cdb93b2de85ebd3666c')
        from google.genai import types
        self.assertEqual(types.Schema.model_validate(engine.v4_schema()).type,types.Type.OBJECT)

    def test_repeated_components_directions_and_interface(self):
        inventory,data=fixture(); rows,report=validate(json.dumps(data),inventory,engine.parse_fmea)
        self.assertEqual(len(rows),6); self.assertEqual(report['structural_status'],'PASS')
        self.assertEqual(report['interfaces_identified'],1)
        self.assertEqual(report['candidate_failure_cases_considered'],54)
        self.assertEqual(report['engineering_status'],'engineering_review_required')

    def test_gaps_unsupported_duplicates_fields_and_truncation(self):
        for mutation in ('unit','direction','interface','duplicate','unsupported','field','rating','incomplete','truncated'):
            inventory,data=fixture()
            if mutation in ('unit','interface'): data['rows']=[r for r in data['rows'] if r['unit_id']!=('u1' if mutation=='unit' else 'u3')]
            if mutation=='direction': data['cases'][8]['applicable']=False; data['cases'][8]['row_ids']=[]
            if mutation=='duplicate': data['rows'].append(data['rows'][0])
            if mutation=='unsupported': data['rows'][0]['unit_id']='invented'
            if mutation=='field': del data['rows'][0]['cause']
            if mutation=='rating': data['rows'][0]['severity']=20
            if mutation=='incomplete': data['complete']=False
            raw=json.dumps(data)
            if mutation=='truncated': raw=raw[:-3]
            with self.subTest(mutation=mutation),self.assertRaises((ValueError,KeyError)): validate(raw,inventory,engine.parse_fmea)

    def test_model_cannot_remove_independent_inventory_unit(self):
        inventory,data=fixture(); data['rows']=[r for r in data['rows'] if r['unit_id']!='u2']; data['cases']=[c for c in data['cases'] if c['unit_id']!='u2']
        report=audit(data,inventory)
        self.assertIn('u2',report['remediation']['missing_unit_ids'])
        self.assertEqual(report['structural_status'],'FAIL')
        inventory['units'].pop(1)
        with self.assertRaisesRegex(ValueError,'Repeated'): audit(data,inventory)

    def test_extraction_is_input_bound_and_hash_checked(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'input.txt'; source.write_text('part | quantity | rate | indication\n- Test motor | 2 | 0.01 | Not provided\n')
            inventory=extract_inventory(source,'synthetic'); self.assertEqual(len(inventory['units']),2)
            path=root/'inventory.json'; path.write_text(json.dumps(inventory)); load_inventory(path,source)
            source.write_text('changed')
            with self.assertRaisesRegex(ValueError,'hash'): load_inventory(path,source)

    def test_v4_generator_is_one_call_and_records_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'input.txt'; source.write_text('synthetic only'); inventory,data=fixture()
            inventory['system_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            path=root/'inventory.json'; path.write_text(json.dumps(inventory))
            with patch('fmea_generator.call_gemini',return_value={'text':json.dumps(data),'finish_reason':'STOP','max_output_tokens':50000}) as call,patch('fmea_generator.automatic_report'),patch('analysis.research.__main__.register'):
                engine.generate_fmea(source,'synthetic',version='v4.0',inventory_file=path,output_dir=root)
            call.assert_called_once(); self.assertEqual(call.call_args.kwargs['version'],'v4.0')
            receipt=json.loads((root/'synthetic_v4.0_run01_execution.json').read_text())
            self.assertEqual(receipt['completeness']['structural_status'],'PASS'); self.assertEqual(len(receipt['git_commit']),40)


class V4ResearchTests(unittest.TestCase):
    def test_missing_data_and_sanitized_build(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); path=root/'judge.json'; path.write_text(json.dumps(import_data()))
            data=build([path],root/'build1',render=False)
            self.assertNotIn('PRIVATE_SENTINEL',json.dumps(data))
            self.assertEqual(len(data['runs']),1); self.assertEqual(data['statistics']['criteria']['mean_below_20'],'PENDING')
            self.assertTrue((root/'build1/validated/items.csv').exists())
            self.assertTrue((root/'build1/validated/analysis.xlsx').exists())
            again=build([path,path],root/'build2',render=False)
            self.assertEqual(data['data_version'],again['data_version'])
            progress=build([],root/'generation-only',render=False)
            self.assertEqual(len(progress['runs']),1)
            before=(root/'current.json').read_bytes(); bad=import_data(); bad['runs'].append(bad['runs'][0]); path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): build([path],root/'bad',render=False)
            self.assertEqual((root/'current.json').read_bytes(),before)

    def test_baseline_pending_and_corrupt_snapshot(self):
        data=empty_snapshot(); validate_snapshot(data)
        self.assertEqual(data['runs'],[]); self.assertEqual(data['statistics']['anova']['status'],'INSUFFICIENT_DATA')
        self.assertTrue(all(v=='PENDING' for v in data['statistics']['criteria'].values()))
        data['private_notes']='forbidden'
        with self.assertRaises(ValueError): validate_snapshot(data)

    def test_stratified_bootstrap_and_primary_anova(self):
        rows=[]
        for version,base in [('v2.0',30),('v3.0',22),('v4.0',12)]:
            for system in 'ABCDE':
                for r in range(4):
                    rows.append({'skill_version':version,'system':system,'missed_percentage':base+r+ord(system)-65,'extra_unmatched_rows':2,'structural_status':'PASS','format_status':'PASS','unsupported_inflation_review':'PASS'})
        ci=bootstrap(rows,('v2.0','v4.0')); self.assertEqual(ci,bootstrap(rows,('v2.0','v4.0')))
        self.assertAlmostEqual(ci['improvement']['percentage_points'],18)
        result=compare(rows)
        self.assertLess(result['anova']['p'],.05); self.assertEqual(result['anova']['df_version'],1)
        self.assertEqual(result['exploratory_three_version']['df_version'],2)
        self.assertTrue(all(v=='PASS' for v in result['criteria'].values()))
        self.assertEqual(anova(rows[:4],('v2.0','v4.0'))['status'],'INSUFFICIENT_DATA')

    def test_registration_preserves_quality_metrics_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); source=root/'receipt.json'
            source.write_text(json.dumps({'workflow':'standalone_gemini','experiment_id':'round2-v4-A-r01','attempt_id':'a','system_id':'system_A','prompt_version':'v4.0','model':'synthetic','status':'success','row_count':2}))
            snapshot=root/'current.json'; atomic_json(snapshot,empty_snapshot())
            first=register(source,snapshot); second=register(source,snapshot)
            self.assertEqual(len(second['registry']),1); self.assertEqual(first['statistics'],second['statistics'])
            self.assertEqual(second['runs'],[])

    def test_human_review_separate_from_ai_judge(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); path=root/'review.json'
            event={'event_id':'synthetic-review-1','run_id':'r','item_id':'i','sample_type':'missed','ai_result':'missed','engineer_result':'found','adjudication_status':'pending','reviewed_at':'2026-11-15T12:00:00+00:00','review_minutes':3}
            path.write_text(json.dumps({'schema':'engineering-review-1','events':[event]}))
            items=[{'run_id':'r','item_id':'i','found':False}]
            result=review_events([path],[{'run_id':'r'}],items)
            self.assertFalse(result[0]['agreement']); self.assertFalse(items[0]['found'])

    def test_review_queue_is_deterministic_and_does_not_invent_missing_strata(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); source=root/'judge.json'; source.write_text(json.dumps(import_data()))
            a=review_sample([source],root/'a.json'); b=review_sample([source],root/'b.json')
            self.assertEqual(a,b)
            self.assertEqual({t['sample_type'] for t in a},{'correct_match','missed','extra'})
            self.assertIsNone(next(t for t in a if t['sample_type']=='extra')['generated_item_id'])

    def test_v4_plan_exclusive_twenty_runs(self):
        with tempfile.TemporaryDirectory(dir='results') as temp:
            root=Path(temp); data=plan(root/'plan','unconfirmed')
            self.assertEqual(len(data['runs']),20); self.assertEqual({r['skill_version'] for r in data['runs']},{'v4.0'})
            self.assertTrue(all(r['run_id'].startswith('round2-v4-') for r in data['runs']))
            with self.assertRaises(FileExistsError): plan(root/'plan','unconfirmed')

if __name__=='__main__': unittest.main()
