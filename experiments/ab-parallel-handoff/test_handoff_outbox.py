import os
import tempfile
import unittest
from handoff_outbox import connect,enqueue,claim_for_dispatch,mark_timeout,record_received,record_verdict

class HandoffOutboxTest(unittest.TestCase):
 def test_durable_replay_conflict_and_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   path=os.path.join(d,"db.sqlite")
   db=connect(path)
   args=("req-1",141,277,"product-sha","base-sha","https://github.com/example/run")
   self.assertEqual(enqueue(db,*args),"QA_PENDING")
   self.assertEqual(enqueue(db,*args),"QA_PENDING")
   with self.assertRaises(ValueError):
    enqueue(db,"req-1",141,278,"different-sha","base-sha","https://github.com/example/run")
   self.assertEqual(db.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0],1)
   self.assertEqual(db.execute("SELECT COUNT(*) FROM handoff_audit WHERE event='HANDOFF_CONFLICT'").fetchone()[0],1)
   self.assertTrue(claim_for_dispatch(db,"req-1",2))
   self.assertTrue(mark_timeout(db,"req-1"))
   self.assertTrue(claim_for_dispatch(db,"req-1",2))
   self.assertFalse(claim_for_dispatch(db,"req-1",2))
   db.close()
   db=connect(path)
   self.assertFalse(record_received(db,"req-1","product-sha"))
   self.assertFalse(record_received(db,"req-1","wrong-sha",evidence={"verified_by_trusted_actions_api":True}))
   self.assertFalse(record_verdict(db,"req-1","product-sha","qa-sha","QA_PASS","url","","READY"))
   self.assertEqual(db.execute("SELECT state FROM handoffs WHERE request_id='req-1'").fetchone()[0],"QA_HANDOFF_TIMEOUT")
   db.close()
if __name__=="__main__": unittest.main()
