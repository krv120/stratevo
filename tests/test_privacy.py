import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app import agent, catalog, matching
from app.privacy import buyer_safe, safe_answer


class PrivacyTests(unittest.TestCase):
    def test_source_link_variants(self):
        for value in ['https://sale.alibaba.com/item/123', 'ALIBABA.COM/item', '//s.alicdn.com/image.jpg', 'alibaba[dot]com', 'alibaba%2Ecom', 'alibaba&#46;com', 'ａｌｉｂａｂａ.com', 'ali\u200bbaba.com']:
            with self.subTest(value=value):
                self.assertIn('remain private',safe_answer('Look here: '+value))
                self.assertNotIn('alibaba',buyer_safe(value).lower())

    def test_official_actions_remain_available(self):
        for value in ['https://app.minup.io/book/stratevo', 'hello@stratevo.co', 'https://stratevo.online', 'MOQ is 3.5 pieces; 7.5ft tree']:
            self.assertEqual(safe_answer(value),value)
        for value in ['https://app.minup.io/book/stratevo?redirect=https://example.com', 'https://stratevo.online.evil.com', 'https://stratevo.online@evil.com']:
            self.assertIn('remain private',safe_answer(value))

    def test_recursive_public_projection(self):
        result=buyer_safe({'description':'tree https://example.com/source','matrix':{'category':'name@example.com'},'claims':['https://s.alicdn.com/certificate']})
        self.assertNotIn('example.com',json.dumps(result))
        self.assertNotIn('alicdn',json.dumps(result))

    @patch.dict(os.environ,{'AI_API_KEY':'test-only','AI_MODEL':'test'})
    def test_model_output_is_filtered_server_side(self):
        answer=agent.reply([{'role':'user','content':'Give me the source'}],lambda messages:{'content':'[Supplier](https://sale.alibaba.com/item)'})
        self.assertNotIn('alibaba',answer['message'])
        self.assertEqual(answer['references'],[])

    def test_import_and_legacy_read_boundaries_keep_original_private(self):
        catalog.PRIVATE.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=catalog.PRIVATE) as directory:
            db=Path(directory)/'test.sqlite3'
            source=Path(directory)/'test.json'
            row={'source_row_id':'998-1','description_summary':'Test tree https://sale.alibaba.com/source', 'advertised_moq':{'quantity':1,'unit':'pieces'}}
            source.write_text(json.dumps({'records':[row]}))
            catalog.import_json(source,db)
            self.assertNotIn('alibaba',json.dumps(catalog.search('tree',db=db)))
            connection=catalog.connect(db)
            try:
                self.assertIn('alibaba',connection.execute('SELECT original FROM records').fetchone()[0])
                # Simulate a previously imported, unsanitized database record.
                public=json.loads(connection.execute('SELECT public_summary FROM records').fetchone()[0])
                public['description']=row['description_summary']
                with connection:connection.execute('UPDATE records SET public_summary=?',(json.dumps(public),))
            finally:connection.close()
            self.assertNotIn('alibaba',json.dumps(catalog.search('tree',db=db)))
            result=matching.match({'product':'tree','volume':10,'unit':'pieces','location':'any','certifications':[]},db)
            self.assertEqual(len(result['matches']),1)
            self.assertNotIn('alibaba',json.dumps(result))

if __name__=='__main__':unittest.main()
