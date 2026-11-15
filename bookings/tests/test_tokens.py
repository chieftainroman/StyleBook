"""
Tests for bookings/tokens.py — the signed links in client emails.

These links are the ONLY thing protecting "cancel my booking" from strangers,
so the important tests are the negative ones: tampering, wrong action,
expiry, garbage input, wrong secret key.
"""
from unittest import mock

from django.test import SimpleTestCase, override_settings

from bookings import tokens
from bookings.tokens import make_action_token, parse_action_token

REF = 'STBK-ABCDE'


class TokenRoundTripTests(SimpleTestCase):
    def test_cancel_token_round_trips(self):
        token = make_action_token(REF, 'cancel')
        self.assertEqual(parse_action_token(token), {'ref': REF, 'action': 'cancel'})

    def test_reschedule_token_round_trips(self):
        token = make_action_token(REF, 'reschedule')
        self.assertEqual(parse_action_token(token), {'ref': REF, 'action': 'reschedule'})

    def test_token_is_safe_to_put_in_a_url_path(self):
        token = make_action_token(REF, 'cancel')
        self.assertRegex(token, r'^[A-Za-z0-9_\-.]+$')
        self.assertNotIn('/', token)

    def test_unknown_action_is_refused_when_making(self):
        with self.assertRaises(ValueError):
            make_action_token(REF, 'delete')


class TokenRejectionTests(SimpleTestCase):
    def test_changed_signature_is_rejected(self):
        token = make_action_token(REF, 'cancel')
        payload, sig = token.rsplit('.', 1)
        flipped = ('A' if sig[0] != 'A' else 'B') + sig[1:]
        self.assertIsNone(parse_action_token(f'{payload}.{flipped}'))

    def test_signature_from_another_booking_is_rejected(self):
        mine = make_action_token(REF, 'cancel')
        theirs = make_action_token('STBK-ZZZZZ', 'cancel')
        forged = theirs.rsplit('.', 1)[0] + '.' + mine.rsplit('.', 1)[1]
        self.assertIsNone(parse_action_token(forged))

    def test_cancel_signature_cannot_be_reused_for_reschedule(self):
        cancel = make_action_token(REF, 'cancel')
        resched = make_action_token(REF, 'reschedule')
        forged = resched.rsplit('.', 1)[0] + '.' + cancel.rsplit('.', 1)[1]
        self.assertIsNone(parse_action_token(forged))

    def test_token_signed_with_a_different_secret_key_is_rejected(self):
        with override_settings(SECRET_KEY='some-other-secret'):
            token = make_action_token(REF, 'cancel')
        self.assertIsNone(parse_action_token(token))

    def test_garbage_input_returns_none_instead_of_crashing(self):
        # (non-ASCII junk currently crashes — see test_known_bugs.py, bug 10)
        for junk in ('', 'abc', '.', 'a.b', '!!!.???', '....', 'x' * 5000):
            with self.subTest(token=junk[:20]):
                self.assertIsNone(parse_action_token(junk))


class TokenExpiryTests(SimpleTestCase):
    def test_token_is_valid_until_its_lifetime_ends(self):
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000):
            token = make_action_token(REF, 'cancel', lifetime=3600)
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000 + 3600):
            self.assertIsNotNone(parse_action_token(token))
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000 + 3601):
            self.assertIsNone(parse_action_token(token))

    def test_default_lifetime_is_30_days(self):
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000):
            token = make_action_token(REF, 'cancel')
        thirty_days = 30 * 24 * 3600
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000 + thirty_days):
            self.assertIsNotNone(parse_action_token(token))
        with mock.patch.object(tokens.time, 'time', return_value=1_000_000 + thirty_days + 1):
            self.assertIsNone(parse_action_token(token))
