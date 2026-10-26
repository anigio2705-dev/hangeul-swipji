"""Public mount must preserve files without exposing the isolated backend/data."""
import http.client
import threading
import unittest
from pathlib import Path
import server

class FreeMountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.thread.join()
    def get(self,path):
        c=http.client.HTTPConnection('127.0.0.1',self.http.server_port)
        c.request('GET',path);r=c.getresponse();status=r.status;body=r.read();c.close();return status,body
    def test_free_content_bytes_preserved(self):
        for f in ['index.html','intro.html','advanced2.html','reading.html','reading-curriculum.js','hangul-audio-manifest.json','teaching-entry.js']:
            status,body=self.get('/free/'+f)
            self.assertEqual(status,200,f);self.assertEqual(body,(server.ROOT.parent/f).read_bytes())
    def test_no_private_files_or_traversal(self):
        for f in ['phase3/server.py','phase3/schema.sql','phase3/content.json','phase3/free-public-files.json','.git/config','.env','../phase3/server.py','%2e%2e/phase3/server.py','assets/../../phase3/server.py','PHASE2-RECHECK-20261027.md']:
            self.assertEqual(self.get('/free/'+f)[0],404,f)
    def test_unknown_public_file_not_exposed(self):
        self.assertEqual(self.get('/free/unlisted.json')[0],404)
