import os
import tempfile
import unittest
from handoff_outbox import connect, enqueue, claim_for_dispatch, mark_timeout, record_received

class HandoffOutboxTest(unittest.TestCase):
    def test_durable_replay_and_sha_fence(self):
        with tempfile.TemporaryDirectory() as d:
            path=os.path.join(d,"handoffs.sqlite")
            db=connect(path)
            args=("req-1",140,266,"product-sha","base-sha","https://github.com/example/run")
            enqueue(db,*args)
            enqueue(db,*args)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM handoffs").fetchone()[0],1)
            self.assertTrue(claim_for_dispatch(db,"req-1",2))
            self.assertTrue(mark_timeout(db,"req-1"))
            self.assertTrue(claim_for_dispatch(db,"req-1",2))
            self.assertFalse(claim_for_dispatch(db,"req-1",2))
            db.close()
            db=connect(path)
            self.assertFalse(record_received(db,"req-1","wrong-sha"))
            self.assertTrue(record_received(db,"req-1","product-sha"))
            self.assertFalse(claim_for_dispatch(db,"req-1"))
            db.close()
if __name__=="__main__": unittest.main()
