import json, os, sqlite3, subprocess, sys, tempfile, unittest
from bootstrap import resume_gate
OLD = "a"*40
NEW = "b"*40
class RecoveryGateTests(unittest.TestCase):
    def test_sha_change_after_restart_blocks_old_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"memory.db")
            before=resume_gate(db,"140",OLD,OLD,OLD,True,True,True,True)
            self.assertEqual(before["state"],"VERIFIED_READY_TO_RESUME")
            script="import json,sys;from bootstrap import resume_gate;print(json.dumps(resume_gate(sys.argv[1],'140','%s','%s','%s',True,True,True,True)))"%(OLD,NEW,OLD)
            p=subprocess.run([sys.executable,"-c",script,db],cwd=os.path.dirname(__file__),capture_output=True,text=True,check=True)
            after=json.loads(p.stdout)
            self.assertEqual(after["state"],"RECOVERY_BLOCKED")
            self.assertFalse(after["execution_allowed"])
            self.assertEqual(sqlite3.connect(db).execute("SELECT state FROM resume_decisions WHERE task_id='140'").fetchone()[0],"RECOVERY_BLOCKED")
    def test_missing_verification_is_not_permission(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=os.path.join(tmp,"memory.db")
            self.assertEqual(resume_gate(db,"140",OLD)["state"],"RECOVERED_UNVERIFIED")
            self.assertEqual(resume_gate(db,"140",OLD,OLD,OLD,False,True,True,True)["state"],"RECOVERED_UNVERIFIED")
            self.assertEqual(resume_gate(db,"140",OLD,OLD,OLD,True,True,False,True)["state"],"RECOVERED_UNVERIFIED")
            self.assertEqual(resume_gate(db,"140",OLD,OLD,OLD,True,True,True,True,conflict=True)["state"],"RECOVERY_BLOCKED")
if __name__=="__main__":unittest.main()
