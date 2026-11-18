import unittest
from diagnostic import TLSJSONTransport, DiagnosticError
DB="a"*32
HEADERS={"Authorization":"Bearer mock", "Notion-Version":"2022-06-28"}
class Reply:
    status=200
    def __init__(self,url,raw=b'{}'): self.url=url;self.raw=raw
    def geturl(self):return self.url
    def read1(self,n):
        chunk=self.raw[:n];self.raw=self.raw[n:];return chunk
    def __enter__(self):return self
    def __exit__(self,*x):pass
class Fake:
    def __init__(self,response):self.response=response
    def open(self,request,timeout):
        assert timeout==20
        return self.response
class Tests(unittest.TestCase):
    def test_bound_and_redirect(self):
        transport=TLSJSONTransport(DB)
        url=f'https://api.notion.com/v1/databases/{DB}/query'
        for response in [Reply(url,b'x'*2_000_001),Reply('https://evil.example'),Reply(url,b'PRIVATE_INVALID_JSON')]:
            transport.opener=Fake(response)
            with self.assertRaisesRegex(DiagnosticError,'^request_failed$'):
                transport('POST',url,{}, HEADERS)
    def test_valid(self):
        transport=TLSJSONTransport(DB);url=f'https://api.notion.com/v1/databases/{DB}/query'
        transport.opener=Fake(Reply(url,b'{"results":[]}'))
        self.assertEqual(transport('POST',url,{},HEADERS),{'results':[]})
if __name__=='__main__':unittest.main()
