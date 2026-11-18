import unittest, ssl, urllib.request, urllib.error
from unittest.mock import Mock
from diagnostic import *
from test_diagnostic import DB,PARENT,metadata
class Gates(unittest.TestCase):
    def run_replies(self,replies,limit=3):
        if len(replies) >= 3:
            replies = [replies[0]] + replies[3:] + replies[1:3]
        def transport(*args):return replies.pop(0)
        return diagnose(ReadOnlyAPI(transport,DB,PARENT),'mobile','password','token',page_limit=limit)
    def base(self):return [metadata(),{'data':{'token':'mock'}},{'data':{'lastTimestamp':0,'records':[]}}]
    def test_target_multipage(self):
        replies=self.base()+[{'results':[],'has_more':True,'next_cursor':'x'},{'results':[],'has_more':False}]
        self.assertEqual(self.run_replies(replies)['status'],'complete')
    def test_target_cursor_and_cycle(self):
        for suffix in [[{'results':[],'has_more':True,'next_cursor':None}], [{'results':[],'has_more':True,'next_cursor':'x'}]*2]:
            self.assertEqual(self.run_replies(self.base()+suffix),{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_both_page_limits(self):
        self.assertEqual(self.run_replies(self.base()+[{'results':[],'has_more':True,'next_cursor':'x'}],1),{'status':'incomplete','latest_edited_sample':'unknown'})
        replies=self.base()+[{'results':[],'has_more':False}];replies[2]['data']['lastTimestamp']=1
        self.assertEqual(self.run_replies(replies,1),{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_invalid_limits(self):
        for limit in (0,-1,101,True,1.5):self.assertEqual(self.run_replies([],limit),{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_target_identity_schema(self):
        for field,value in [('id','c'*32),('archived',True),('properties',{})]:
            meta=metadata();meta[field]=value
            self.assertEqual(self.run_replies([meta]),{'status':'incomplete','latest_edited_sample':'unknown'})
        meta=metadata();meta['parent']['page_id']='d'*32
        self.assertEqual(self.run_replies([meta]),{'status':'incomplete','latest_edited_sample':'unknown'})
    def test_transport_direct_block(self):
        transport=TLSJSONTransport(DB)
        transport.opener=Mock() # verify validation rejects before any network entry
        for method,url,headers in [('POST','https://evil.example',{}),('POST','https://api.notion.com/v1/pages',{}),('POST','https://api.gotokeep.com/v1.1/users/login',{'Host':'evil.example'})]:
            with self.assertRaises(DiagnosticError):transport(method,url,{},headers)
            transport.opener.open.assert_not_called()
    def test_real_redirect_handler_rejects(self):
        transport=TLSJSONTransport(DB)
        redirect=next(x for x in transport.opener.handlers if isinstance(x,urllib.request.HTTPRedirectHandler))
        # Call urllib's actual HTTP error processing path; must reject, not issue next hop.
        request=urllib.request.Request('https://api.gotokeep.com/v1.1/users/login',data=b'mock')
        for code in (301,302,303,307,308):
            with self.assertRaises(urllib.error.HTTPError):
                transport.opener.error('http',request,None,code,'redirect',{'location':'https://evil.example'})
    def test_tls_verification_and_deadline(self):
        transport=TLSJSONTransport(DB)
        handler=next(x for x in transport.opener.handlers if isinstance(x,urllib.request.HTTPSHandler))
        self.assertTrue(handler._context.check_hostname)
        self.assertEqual(handler._context.verify_mode,ssl.CERT_REQUIRED)
        transport.deadline=0
        with self.assertRaises(DiagnosticError):transport('POST','https://api.gotokeep.com/v1.1/users/login',{}, {})
if __name__=='__main__':unittest.main()
