import unittest, os
from unittest.mock import patch
import runner
class RunnerTests(unittest.TestCase):
    def test_no_target_fails_before_transport(self):
        with patch.dict(os.environ,{'NOTION_TOKEN':'mock','NOTION_PAGE':'b'*32,'KEEP_MOBILE':'mock','KEEP_PASSWORD':'mock'},clear=True), patch('diagnostic.TLSJSONTransport') as transport:
            self.assertEqual(runner.run(),{'status':'configuration_unavailable'})
            transport.assert_not_called()
    def test_invalid_target_fails_before_transport(self):
        with patch.dict(os.environ,{'NOTION_TOKEN':'mock','NOTION_PAGE':'b'*32,'NOTION_WORKOUT_DATABASE_ID':'invalid','KEEP_MOBILE':'mock','KEEP_PASSWORD':'mock'},clear=True), patch('diagnostic.TLSJSONTransport') as transport:
            with self.assertRaises(Exception):runner.run()
            transport.assert_not_called()
if __name__=='__main__':unittest.main()
