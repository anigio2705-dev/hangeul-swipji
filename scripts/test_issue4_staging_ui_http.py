"""Issue #4: inspect real gated HTTP homepage/assets and official learner APIs.
Runs actual ThreadingHTTPServer and temporary SQLite; no deployment and no money.
"""
import json
import unittest
from test_staging import StagingTests as Harness

class Issue4PreviewHTTP(unittest.TestCase):
    setUp=Harness.setUp
    tearDown=Harness.tearDown
    request=Harness.request
    register=Harness.register

    def test_real_homepage_and_lesson_assets_behind_gate(self):
        code,_,raw=self.request("/",authenticated=False)
        self.assertEqual(code,401)
        self.assertNotIn(b"hs-issue4-preview-notice",raw)
        code,headers,raw=self.request("/")
        self.assertEqual(code,200)
        self.assertIn(b"hs-issue4-preview-notice",raw)
        self.assertIn(b"team12_learning_handoff.js",raw)
        self.assertIn(b"teaching-platform",raw)
        for path in ("/learn.html","/intro.html","/beginner1.html",
                     "/scripts/team12_learning_handoff.js",
                     "/scripts/team12_server_progress.js",
                     "/scripts/team12_resume.js",
                     "/scripts/team12_provider_links.js",
                     "/phase3/app.js",
                     "/phase3/instant-speaking.html"):
            code,_,body=self.request(path)
            print("GET",path,"HTTP",code,"bytes",len(body),flush=True)
            self.assertEqual(code,200,(path,body[:140]))
            self.assertGreater(len(body),100,path)
        code,_,raw=self.request("/healthz",authenticated=False)
        self.assertEqual(code,200)
        self.assertTrue(json.loads(raw)["ok"])

    def test_signup_progress_quiz_resume_relogin_same_origin(self):
        code,_,raw=self.register("issue4-learner@example.test")
        self.assertEqual(code,200,raw)
        for path,data in (("/api/free-progress",{"stage":1,"lesson":1}),
            ("/api/free-progress/quiz",{"stage":1,"lesson":1,"score":5,"maxScore":5,"requestId":"issue4-quiz-1"}),
            ("/api/free-progress/position",{"stage":1,"lesson":2})):
            code,_,raw=self.request(path,data)
            self.assertEqual(code,200,(path,raw))
        self.assertEqual(self.request("/api/logout",{})[0],200)
        code,_,raw=self.request("/api/login",{"email":"issue4-learner@example.test","password":"Learner-Password-12345!"})
        self.assertEqual(code,200,raw)
        self.assertEqual(json.loads(self.request("/api/free-progress")[2])["count"],1)
        self.assertEqual(json.loads(self.request("/api/free-progress/quiz")[2])["count"],1)
        self.assertEqual(json.loads(self.request("/api/free-progress/position")[2])["position"]["lesson"],2)

del Harness
if __name__=="__main__":
    unittest.main(verbosity=2)
