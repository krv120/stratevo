import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import agent, catalog, matching


class MatchingTests(unittest.TestCase):
    def setUp(self):
        catalog.PRIVATE.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=catalog.PRIVATE)
        self.db = Path(self.tmp.name) / 'test.sqlite3'
        rows=[]
        for i in range(1,8):
            rows.append({'source_row_id':f'991-{i}', 'description_summary':f'Christmas tree model {i}', 'supplier_as_listed_private':'SECRET FACTORY', 'advertised_moq':{'quantity':10,'unit':'pieces'}, 'matrix':{'category':'consumer_products','location':'China','certifications_claimed':['CE'],'certifications_verified':['CE'],'supplier_contact':'SECRET CONTACT'}})
        self.file=Path(self.tmp.name)/'test.json'
        self.file.write_text(json.dumps({'records':rows}))
        catalog.import_json(self.file,self.db)
        self.requirement={'product':'Christmas tree','volume':100,'unit':'pieces','location':'any','certifications':[]}

    def tearDown(self):
        self.tmp.cleanup()

    def test_four_points_gate_precedes_database_read(self):
        for key in matching.REQUIRED:
            requirement={k:v for k,v in self.requirement.items() if k != key}
            with patch('app.matching.catalog.count') as count:
                result=matching.match(requirement,self.db)
                count.assert_not_called()
            self.assertEqual(result['status'],'needs_qualification')
            self.assertEqual(result['matches'],[])

    def test_three_max_and_no_private_metadata_or_fake_verification(self):
        result=matching.match(self.requirement,self.db)
        self.assertEqual(len(result['matches']),3)
        self.assertEqual(result['reviewed_product_candidates'],7)
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertNotIn('source_row_id',json.dumps(result))
        for row in result['matches']:
            self.assertEqual(row['matrix']['certifications_verified'],[])
            self.assertEqual(row['moq_match'],'Yes — advertised MOQ only')
        self.assertIn('Why they fit:',matching.render(result))

    def test_certification_claim_is_not_evidence(self):
        result=matching.match({**self.requirement,'certifications':['CE']},self.db)
        self.assertEqual(result['matches'],[])
        self.assertIn('not verified',str(result['evidence_gaps']))
        self.assertIn(matching.BOOKING,result['message'])
        self.assertNotIn('flagging',result['message'])

    def test_location_moq_and_unit_constraints(self):
        for override in ({'location':'Germany'}, {'volume':1}, {'unit':'sets'}):
            self.assertEqual(matching.match({**self.requirement,**override},self.db)['matches'],[])

    def test_unknown_moq_is_not_yes(self):
        rows=json.loads(self.file.read_text())
        for row in rows['records']:row['advertised_moq']['unit']=None
        self.file.write_text(json.dumps(rows));catalog.import_json(self.file,self.db)
        self.assertEqual(matching.match(self.requirement,self.db)['matches'],[])

    def test_missing_optional_evidence_cannot_satisfy_constraint(self):
        for override in ({'lead_time_days':30},{'target_price':20,'currency':'EUR'}):
            self.assertEqual(matching.match({**self.requirement,**override},self.db)['matches'],[])

    def test_all_product_tokens_required(self):
        self.assertEqual(matching.match({**self.requirement,'product':'Christmas steel bearing'},self.db)['matches'],[])

    def test_invalid_values(self):
        for override in ({'volume':True},{'volume':float('nan')},{'volume':-1},{'certifications':'none'},{'certifications':['']},{'unit':[]},{'target_price':3},{'location':'   '}):
            with self.assertRaises(ValueError):matching.match({**self.requirement,**override},self.db)

    @patch.dict(os.environ,{'AI_API_KEY':'fake-test-key','AI_MODEL':'test'})
    def test_old_unqualified_model_tool_cannot_search(self):
        provider=lambda messages:{'tool_calls':[{'function':{'name':'match_catalog','arguments':'{"product":"tree"}'}}]}
        with patch('app.matching.catalog.count') as count:
            result=agent.reply([{'role':'user','content':'Find a tree'}],provider)
            count.assert_not_called()
        self.assertEqual(result['references'],[])
        self.assertIn('Before matching',result['message'])

    @patch.dict(os.environ,{'AI_API_KEY':'fake-test-key','AI_MODEL':'test'})
    def test_parallel_queries_cannot_bypass_cap(self):
        call={'function':{'name':'match_catalog','arguments':json.dumps(self.requirement)}}
        with self.assertRaises(ValueError):agent.reply([{'role':'user','content':'Find trees'}],lambda messages:{'tool_calls':[call,call]})

if __name__=='__main__':unittest.main()
