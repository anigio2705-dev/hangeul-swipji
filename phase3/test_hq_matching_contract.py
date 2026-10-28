"""Pure matching-event validation; no external video, DB or payments."""
import unittest
import server
import instant_matching as matching

class MatchingContractTests(unittest.TestCase):
    def test_valid_contract(self):
        e=matching.transaction_event_contract('booking-1','event-1','lesson.completed')
        self.assertEqual('booking-1',e['bookingId']);self.assertFalse(e['paymentExecuted'])
    def test_invalid_ids_rejected_before_db_access(self):
        for bad in ('',' ',' event','event ','x'*129,'a\nb',None,True,1):
            with self.subTest(bad=bad),self.assertRaises(server.Error):
                matching.transaction_event_contract(bad,'event','lesson.started')
            with self.subTest(event=bad),self.assertRaises(server.Error):
                matching.transaction_event_contract('booking',bad,'lesson.started')
            with self.subTest(record=bad),self.assertRaises(server.Error):
                matching.record_lesson_event(None,None,'booking',bad,'lesson.started')
    def test_month_id_and_lesson_index_bounded(self):
        for bad in ('',' ','month ','m'*129,'m\n1',True):
            with self.subTest(month=bad),self.assertRaises(server.Error):
                matching.transaction_event_contract('b','e','lesson.completed',month_id=bad,lesson_index=0)
        for bad in (-1,True,10001,1.5):
            with self.subTest(index=bad),self.assertRaises(server.Error):
                matching.transaction_event_contract('b','e','lesson.completed',month_id='m',lesson_index=bad)
        self.assertEqual(10000,matching.transaction_event_contract('b','e','lesson.completed',month_id='m',lesson_index=10000)['lessonIndex'])
if __name__=='__main__':unittest.main()
