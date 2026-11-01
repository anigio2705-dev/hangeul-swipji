"""#110 isolated real HTTP GET: trusted session-bound, nonbinding reward explanation."""
import unittest

import server
from test_server import Client, PlatformTests


class ReferralRewardExplanationHttpTests(unittest.TestCase):
    setUp = PlatformTests.setUp
    tearDown = PlatformTests.tearDown
    register = PlatformTests.register
    book = PlatformTests.book
    booking = PlatformTests.booking

    @staticmethod
    def url(booking_id):
        return '/api/referrals/reward-explanation?bookingId=' + booking_id

    def test_01_learner_teacher_admin_receive_only_own_policy_unverified_view(self):
        bid = self.booking()
        for client, role in ((self.learner, 'learner'),
                             (self.teacher, 'teacher'),
                             (self.admin, 'platform')):
            with self.subTest(role=role):
                status, result = client.call(self.url(bid))
                self.assertEqual(200, status, result)
                self.assertEqual(role, result['view']['role'])
                self.assertEqual('POLICY_UNVERIFIED', result['view']['state'])
                self.assertIsNone(result['view']['hypothetical_candidate_krw'])
                self.assertFalse(result['view']['business_policy_approved'])
                self.assertFalse(result['view']['live_payout_enabled'])
                self.assertFalse(result['view']['original_contract_ready'])
                self.assertFalse(result['approvedPolicy'])
                self.assertFalse(result['realMoneyEnabled'])
                self.assertTrue(result['reviewOnly'])

    def test_02_outsider_cannot_enumerate_booking(self):
        bid = self.booking()
        self.assertEqual(403, self.outsider.call(self.url(bid))[0])
        self.assertEqual(403, self.outsider.call(self.url('missingbooking'))[0])

    def test_03_missing_and_expired_cookie_fail_closed(self):
        bid = self.booking()
        self.assertEqual(401, Client(self.http.server_port).call(self.url(bid))[0])
        with server.connect() as db:
            db.execute('UPDATE sessions SET expires=? WHERE user_id=?',
                       (self.clock - 1, self.l['id']))
        self.assertEqual(401, self.learner.call(self.url(bid))[0])

    def test_04_forged_actor_role_policy_and_repeated_booking_rejected(self):
        bid = self.booking()
        for suffix in ('&actorId=' + self.t['id'], '&role=admin',
                       '&approvedPolicy=true', '&paymentVerified=true',
                       '&bookingId=' + bid):
            with self.subTest(suffix=suffix):
                self.assertEqual(400, self.learner.call(self.url(bid) + suffix)[0])
        self.assertEqual(400, self.learner.call(
            '/api/referrals/reward-explanation')[0])

    def test_05_invalid_id_rejected_and_missing_id_not_found_without_leak(self):
        self.assertEqual(400, self.learner.call(
            '/api/referrals/reward-explanation?bookingId=../bad')[0])
        self.assertEqual(403, self.learner.call(self.url('notfound'))[0])

    def test_06_referrer_must_be_bound_in_persistent_db(self):
        with server.connect() as db:
            code = db.execute('SELECT referral_code FROM users WHERE id=?',
                              (self.o['id'],)).fetchone()[0]
        invited, _ = self.register('learner', 'invited-http-110', code)
        status, result = self.book(client=invited)
        self.assertEqual(200, status, result)
        bid = result['bookingId']
        status, response = self.outsider.call(self.url(bid))
        self.assertEqual(200, status, response)
        self.assertEqual('referrer', response['view']['role'])
        self.assertIsNone(response['view']['hypothetical_candidate_krw'])
        self.assertEqual(403, self.learner.call(self.url(bid))[0])

    def test_07_booking_slot_teacher_mismatch_denied_at_http_boundary(self):
        bid = self.booking()
        _, second = self.register('teacher', 'second-http-110')
        with server.connect() as db:
            db.execute('UPDATE bookings SET teacher_id=? WHERE id=?',
                       (second['id'], bid))
        self.assertEqual(403, self.learner.call(self.url(bid))[0])
        self.assertEqual(403, self.teacher.call(self.url(bid))[0])

    def test_08_read_only_preview_does_not_create_reward_or_ledger(self):
        bid = self.booking()
        with server.connect() as db:
            before = db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]
        for client in (self.learner, self.teacher, self.admin):
            self.assertEqual(200, client.call(self.url(bid))[0])
        with server.connect() as db:
            after = db.execute('SELECT COUNT(*) FROM ledger').fetchone()[0]
        self.assertEqual(before, after)

    def test_09_post_cannot_turn_preview_into_a_write(self):
        bid = self.booking()
        status, result = self.learner.call(
            '/api/referrals/reward-explanation',
            {'bookingId': bid, 'approvedPolicy': True, 'payout': True})
        self.assertEqual(404, status, result)
        self.assertNotIn('view', result)


if __name__ == '__main__':
    unittest.main()
