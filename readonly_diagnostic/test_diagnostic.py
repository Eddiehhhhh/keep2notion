import unittest
from diagnostic import ReadOnlyAPI, DiagnosticError, diagnose
DB='a'*32
PARENT='b'*32
def metadata(): return {'object':'database','id':DB,'archived':False,'parent':{'type':'page_id','page_id':PARENT},'properties':{'Id':{'type':'rich_text'}}}
class Tests(unittest.TestCase):
    def run_case(self, replies):
        calls=[]
        if len(replies) == 3 and isinstance(replies[-1],dict) and 'records' in replies[-1].get('data', {}):
            replies = [self.target()] + replies
        elif len(replies) == 3:
            replies = [replies[2], replies[0], replies[1]]
        elif len(replies) == 2:
            replies = [self.target()] + replies
        elif len(replies) == 1:
            replies = [self.target()] + replies
        replies.insert(0, metadata())
        def transport(method,url,payload,headers):
            calls.append((method,url,payload,headers))
            response=replies.pop(0)
            if isinstance(response,Exception): raise response
            return response
        result=diagnose(ReadOnlyAPI(transport,DB,PARENT),'PRIVATE_MOBILE','PRIVATE_PASSWORD','PRIVATE_NOTION_TOKEN',page_limit=3)
        self.assertNotIn('PRIVATE',repr(result))
        return result,calls
    def source(self,last=0):
        return {'data':{'lastTimestamp':last,'records':[{'logs':[{'type':'stats','stats':{'id':'PRIVATE_ID','isDoubtful':False}}]}]}}
    def login(self): return {'data':{'token':'PRIVATE_KEEP_TOKEN'}}
    def target(self): return {'results':[],'has_more':False}
    def test_success(self):
        result,calls=self.run_case([self.login(),self.source(),self.target()])
        self.assertEqual(result['candidate_non_doubtful_count'],1)
        self.assertEqual(result['latest_edited_sample'],'unknown')
        self.assertEqual(len(calls),4)
    def test_match(self):
        target={'results':[{'properties':{'Id':{'rich_text':[{'plain_text':'PRIVATE_ID'}]}}}],'has_more':False}
        result,_=self.run_case([self.login(),self.source(),target])
        self.assertEqual(result['candidate_missing_count'],0)
        self.assertEqual(result['latest_edited_sample'],'found')
    def test_errors_redacted(self):
        for replies in ([RuntimeError('PRIVATE')],[{}],[self.login(),{}],[self.login(),self.source(),RuntimeError('PRIVATE')]):
            self.assertEqual(self.run_case(list(replies))[0],{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_cycle(self):
        self.assertEqual(self.run_case([self.login(),self.source(1),self.source(1)])[0],{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_disallowed_requests(self):
        api=ReadOnlyAPI(lambda *x:self.fail('transport reached'),DB,PARENT)
        for method,url in [('PATCH','https://api.notion.com/v1/pages/id'),('POST','https://api.notion.com/v1/pages'),('GET','https://evil.example'),('GET','https://api.gotokeep.com.evil.example'),('GET','https://api.gotokeep.com/pd/v3/stats/detail?dateUnit=all&type=all&lastDate=0&x=secret')]:
            with self.assertRaises(DiagnosticError): api.request(method,url)
    def test_no_entrypoint(self):
        import diagnostic
        self.assertFalse(hasattr(diagnostic,'main'))
if __name__=='__main__': unittest.main()
