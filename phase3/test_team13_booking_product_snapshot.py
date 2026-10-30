"""Team13 booking snapshot is an immutable server decision, never a browser price."""
import sqlite3
import unittest

import instant_matching
import server
from test_team14_instant_http_settlement import InstantSettlementJourney as Journey


class BookingProductSnapshotTests(unittest.TestCase):
    setUp = Journey.setUp
    tearDown = Journey.tearDown
    request = Journey.request
    account = Journey.account
    call = Journey.call

    def make_instant_booking(self, price):
        learner, _ = self.account('snapshot-learner@example.test')
        partner, partner_id = self.account('snapshot-partner@example.test', 'partner', True)
        with server.connect() as db:
            db.execute('UPDATE users SET price=? WHERE id=?', (price, partner_id))
        self.assertEqual('waiting', self.call(learner, 'join')['state'])
        offer = self.call(partner, 'join')
        self.assertEqual('offered', offer['state'])
        self.call(learner, 'ready', {'matchId': offer['matchId']})
        self.call(partner, 'ready', {'matchId': offer['matchId']})
        return self.call(learner, 'session')['bookingId']

    def test_catalog_booking_is_persisted_atomically_and_immutable(self):
        booking_id = self.make_instant_booking(10000)
        with server.connect() as db:
            record = db.execute('SELECT product_code,duration_minutes,price_krw,currency '
                                'FROM booking_product_snapshots WHERE booking_id=?',
                                (booking_id,)).fetchone()
            self.assertEqual(tuple(record), ('partner_25', 25, 10000, 'KRW'))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('UPDATE booking_product_snapshots SET price_krw=6000 '
                           'WHERE booking_id=?', (booking_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM booking_product_snapshots WHERE booking_id=?',
                           (booking_id,))
            self.assertEqual(10000, db.execute('SELECT price_krw FROM booking_product_snapshots '
                                               'WHERE booking_id=?', (booking_id,)).fetchone()[0])

    def test_non_catalog_instant_chat_remains_usable_but_not_settleable(self):
        booking_id = self.make_instant_booking(20000)
        with server.connect() as db:
            self.assertEqual('in_class', db.execute('SELECT status FROM bookings WHERE id=?',
                                                     (booking_id,)).fetchone()[0])
            self.assertIsNone(db.execute('SELECT * FROM booking_product_snapshots '
                                         'WHERE booking_id=?', (booking_id,)).fetchone())

    def test_product_choice_requires_approved_role_and_exact_server_price(self):
        choose = instant_matching.server_test_product_choice
        self.assertIsNone(choose({'approved': 0, 'role': 'partner', 'price': 10000}))
        self.assertIsNone(choose({'approved': 1, 'role': 'partner', 'price': 15000}))
        self.assertIsNone(choose({'approved': 1, 'role': 'teacher', 'price': 10000}))
        self.assertEqual(('professional_25', 25, 15000),
                         choose({'approved': 1, 'role': 'teacher', 'price': 15000}))


if __name__ == '__main__':
    unittest.main(verbosity=2)
