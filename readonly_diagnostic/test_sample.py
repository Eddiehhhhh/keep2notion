import unittest
from diagnostic import ReadOnlyAPI, diagnose
from test_diagnostic import DB,PARENT,metadata
class Samples(unittest.TestCase):
    def evaluate(self, identifiers, source_ids):
        replies=[metadata(),{'results':[{'properties':{'Id':{'rich_text':[{'plain_text':value}] if value else []}}} for value in identifiers], 'has_more':False}, {'data':{'token':'mock'}}, {'data':{'lastTimestamp':0,'records':[{'logs':[{'type':'stats','stats':{'id':value}} for value in source_ids]}]}}]
        def transport(method,url,payload,headers):
            if url.endswith('/query'):
                self.assertEqual(payload['sorts'],[{'timestamp':'last_edited_time','direction':'descending'}])
            return replies.pop(0)
        result=diagnose(ReadOnlyAPI(transport,DB,PARENT),'mock','mock','mock')
        self.assertNotIn('PRIVATE',repr(result))
        return result['latest_edited_sample']
    def test_exact_match(self):self.assertEqual(self.evaluate(['PRIVATE_FIRST'],['PRIVATE_FIRST']),'found')
    def test_not_other_record(self):self.assertEqual(self.evaluate(['PRIVATE_FIRST','PRIVATE_SECOND'],['PRIVATE_SECOND']),'unknown')
    def test_empty_no_fallback(self):self.assertEqual(self.evaluate(['','PRIVATE_SECOND'],['PRIVATE_SECOND']),'unknown')
    def test_no_records(self):self.assertEqual(self.evaluate([],['PRIVATE_FIRST']),'unknown')
    def test_duplicate_same_id(self):self.assertEqual(self.evaluate(['PRIVATE_FIRST','PRIVATE_FIRST'],['PRIVATE_FIRST']),'found')
if __name__=='__main__':unittest.main()
