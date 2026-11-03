import json
import os
import unittest
from unittest.mock import patch
import supabase_auth as auth

class SupabaseAuthContractTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'HS_SUPABASE_TEST_PROJECT_REF':'abcdefghijklmnopqrst','HS_SUPABASE_TEST_PUBLISHABLE_KEY':'sb_publishable_contract_test_only','HS_SUPABASE_TEST_ONLY':'yes'});self.env.start()
        self.user={'id':'11111111-1111-4111-8111-111111111111','email':'learner@example.test','email_confirmed_at':'2026-10-27T00:00:00Z','aud':'authenticated','role':'authenticated','is_anonymous':False,'user_metadata':{'role':'admin'},'app_metadata':{'role':'admin'}}
    def tearDown(self):self.env.stop()
    def test_network_verified_identity_ignores_self_asserted_roles(self):
        seen=[]
        def transport(req):seen.append(req);return json.dumps(self.user).encode()
        result=auth.verify_user('test-token-'+'x'*50,transport)
        self.assertNotIn('role',result);self.assertEqual(self.user['id'],result['subject']);self.assertEqual('https://abcdefghijklmnopqrst.supabase.co/auth/v1/user',seen[0].full_url)
    def test_production_target_and_secret_keys_fail_before_network(self):
        for values in [{'HS_SUPABASE_TEST_PROJECT_REF':auth.PRODUCTION_REF},{'HS_SUPABASE_TEST_PUBLISHABLE_KEY':'sb_secret_never_use'},{'HS_SUPABASE_TEST_ONLY':'no'}]:
            with patch.dict(os.environ,values),self.assertRaises(auth.AuthError):auth.verify_user('x'*50,lambda r:self.fail('network must not run'))
    def test_unverified_anonymous_and_malformed_identity_rejected(self):
        for changes in [{'is_anonymous':True},{'email_confirmed_at':None},{'id':'not-a-uuid'},{'aud':'anon'},{'role':'service_role'}]:
            value=dict(self.user,**changes)
            with self.assertRaises(auth.AuthError):auth.verify_user('x'*50,lambda r:json.dumps(value).encode())
    def test_credentials_not_configured_is_explicit(self):
        with patch.dict(os.environ,{'HS_SUPABASE_TEST_PUBLISHABLE_KEY':''}),self.assertRaises(auth.NotConfigured):auth.verify_user('x'*50)
