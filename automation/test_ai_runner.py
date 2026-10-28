import unittest
from ai_runner import TASKS, validate_payload

class AIRunnerTests(unittest.TestCase):
    def test_allowlist_rejects_other_file(self):
        with self.assertRaises(ValueError):
            validate_payload(TASKS['d2-contract-fixture'],{'path':'main.py','content':'x'*200})
    def test_must_preserve_regression(self):
        with self.assertRaises(ValueError):
            validate_payload(TASKS['d2-contract-fixture'],{'path':TASKS['d2-contract-fixture']['input'],'content':'x'*200})
    def test_valid_proposal(self):
        data={'path':TASKS['d2-contract-fixture']['input'],'content':'def test_http_verified_completion_75_25_refund_replay_restart(self):\n    pass\n'+'#'*150}
        self.assertEqual(validate_payload(TASKS['d2-contract-fixture'],data),data)
    def test_extra_keys_rejected(self):
        with self.assertRaises(ValueError):
            validate_payload(TASKS['d2-contract-fixture'],{'path':'x','content':'y','command':'rm -rf /'})
if __name__=='__main__': unittest.main()
