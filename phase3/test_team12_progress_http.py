"""Real HTTP + SQLite regression for team12's authenticated seven-stage progress API."""
import unittest
from test_server import PlatformTests, Client
import server

class FreeProgressHTTPTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register

    def test_two_browsers_relogin_isolation_and_sqlite(self):
        student_a=self.learner
        student_b=self.outsider
        self.assertEqual(200,student_a.call('/api/free-progress',{'stage':1,'lesson':1})[0])
        self.assertEqual(200,student_a.call('/api/free-progress',{'stage':7,'lesson':50})[0])
        self.assertEqual(200,student_a.call('/api/free-progress',{'stage':1,'lesson':1})[0])
        status,record=student_a.call('/api/free-progress')
        self.assertEqual(200,status)
        self.assertEqual(2,record['count'],'duplicate completions must be idempotent')
        status,other=student_b.call('/api/free-progress')
        self.assertEqual(200,status)
        self.assertEqual(0,other['count'],'member B must not see member A')
        browser2=Client(self.http.server_port)
        self.assertEqual(200,browser2.call('/api/login',{'email':'learner@example.com','password':'Password12345!'})[0])
        self.assertEqual(record['completed'],browser2.call('/api/free-progress')[1]['completed'])
        self.assertEqual(200,student_a.call('/api/logout',{})[0])
        self.assertEqual(401,student_a.call('/api/free-progress')[0])
        with server.connect() as db:
            rows=db.execute('SELECT user_id,stage,lesson FROM free_lesson_progress ORDER BY stage,lesson').fetchall()
            self.assertEqual([(self.l['id'],1,1),(self.l['id'],7,50)],[(x['user_id'],x['stage'],x['lesson']) for x in rows])
        self.assertEqual(400,browser2.call('/api/free-progress',{'stage':8,'lesson':1})[0])
        self.assertEqual(400,browser2.call('/api/free-progress',{'stage':1,'lesson':51})[0])

if __name__=='__main__': unittest.main(verbosity=2)
