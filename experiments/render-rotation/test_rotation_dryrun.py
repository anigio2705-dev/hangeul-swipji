import os
import sqlite3
import tempfile
import unittest
import rotation_dryrun as r

class RotationTests(unittest.TestCase):
    def test_sequence_across_hour(self):
        self.assertEqual([r.slot(r.EPOCH+i*240)[1] for i in range(8)], ["C","D","A","B"]*2)
        self.assertEqual(r.slot(r.EPOCH+3600)[1], "B")  # 15 four-minute slots; no reset at hour boundary
        self.assertEqual(r.slot(r.EPOCH+3840)[1], "C")  # next slot continues the cycle
    def test_idempotent(self):
        with sqlite3.connect(":memory:") as db:
            r.init(db)
            self.assertTrue(r.record(db,r.EPOCH))
            self.assertFalse(r.record(db,r.EPOCH+1))
            self.assertEqual(db.execute("select count(*) from ticks").fetchone()[0],1)
    def test_lag(self):
        seq,team,due=r.slot(r.EPOCH+241)
        self.assertEqual((seq,team,due),(1,"D",r.EPOCH+240))
if __name__=="__main__":unittest.main()
