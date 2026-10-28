"""Actual HTTP regression for safe browser progress import and origin rejection."""
import unittest
from test_common_http_free_progress import FreeProgressHttpTests

class LegacyProgressImportTests(FreeProgressHttpTests):
    def request_import(self,uid,completed):
        import http.client,json
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=5)
        headers={"Content-Type":"application/json"}
        if uid: headers["Cookie"]="hs3=session-token-"+uid
        try:
            conn.request("POST","/api/free-progress/import",json.dumps({"completed":completed}),headers)
            response=conn.getresponse()
            return response.status,json.loads(response.read())
        finally:
            conn.close()

    def test_import_merges_and_retries_without_duplicates(self):
        payload=[{"stage":2,"lesson":3},{"stage":2,"lesson":3},{"stage":7,"lesson":50}]
        self.assertEqual(self.request_import("learner-a",payload)[0],200)
        self.assertEqual(self.request_import("learner-a",payload)[1]["imported"],0)
        status,result=self.request("learner-a")
        self.assertEqual(status,200)
        self.assertTrue({(2,3),(7,50)}.issubset({(x["stage"],x["lesson"]) for x in result["completed"]}))

    def test_import_isolation_and_authentication(self):
        self.assertEqual(self.request_import(None,[{"stage":1,"lesson":1}])[0],401)
        self.assertEqual(self.request_import("provider",[{"stage":1,"lesson":1}])[0],403)
        self.assertEqual(self.request("learner-b")[1]["completed"],[])

    def test_invalid_import_is_atomic(self):
        self.assertEqual(self.request_import("learner-a",[{"stage":1,"lesson":1},{"stage":0,"lesson":1}])[0],400)
        self.assertNotIn((1,1),{(x["stage"],x["lesson"]) for x in self.request("learner-a")[1]["completed"]})

    def test_cross_origin_write_rejected(self):
        import http.client,json
        conn=http.client.HTTPConnection("127.0.0.1",self.http.server_port,timeout=5)
        try:
            conn.request("POST","/api/free-progress",json.dumps({"stage":1,"lesson":1}),
                         {"Content-Type":"application/json","Cookie":"hs3=session-token-learner-a",
                          "Origin":"https://untrusted.example"})
            response=conn.getresponse()
            self.assertEqual(response.status,403)
            response.read()
        finally:
            conn.close()

if __name__=="__main__":
    unittest.main()
