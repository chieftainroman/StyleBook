"""
Tests for the PUBLIC booking flow — what a client does without an account:

    /book/<username>/                    booking page
    /book/<username>/api/availability/   slots for a day
    /book/<username>/api/summary/        which days have slots
    /book/<username>/create/             create pending booking + send OTP
    /book/<username>/verify-otp/         confirm with the 6-digit code
    /book/<username>/resend-otp/         new code

This is exactly what Monday's first clients will click through.
"""
import json
import re
from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import Client, TestCase
from django.utils import timezone

from bookings.models import Booking, OTPRequest
from core.factories import day_at, future_day, make_booking, make_master, make_otp, make_service


class BookingTestCase(TestCase):
    """Shared setup: master 'ana', open 09–18 every day, one 30-min haircut."""

    def setUp(self):
        self.master = make_master('ana')
        self.cut = make_service(self.master, 'Haircut', minutes=30, price='40.00')
        self.day = future_day(7)
        self.slot = day_at(self.day, '10:00')

    def post_json(self, url, payload, **extra):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json', **extra)

    def create(self, **overrides):
        payload = {
            'service_id': self.cut.id,
            'slot_iso': self.slot.isoformat(),
            'client_name': 'Jordan Client',
            'client_email': 'jordan@example.com',
            'client_phone': '+1 555 0199',
            'client_notes': 'Low fade please',
            'source': 'qr',
        }
        payload.update(overrides)
        return self.post_json('/book/ana/create/', payload)

    def verify(self, ref, code):
        return self.post_json('/book/ana/verify-otp/', {'reference_code': ref, 'code': code})

    def latest_code(self, ref):
        return OTPRequest.objects.filter(booking__reference_code=ref).order_by('-created_at', '-id').first().code


class BookPageTests(BookingTestCase):
    def test_open_master_shows_only_active_services(self):
        make_service(self.master, 'Secret menu', active=False)
        response = self.client.get('/book/ana/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'bookings/book.html')
        self.assertEqual(list(response.context['services']), [self.cut])

    def test_master_who_has_not_finished_onboarding_is_not_bookable(self):
        self.master.onboarding_completed = False
        self.master.save()
        response = self.client.get('/book/ana/')
        self.assertTemplateUsed(response, 'bookings/not_available.html')

    def test_master_without_active_services_is_not_bookable(self):
        self.cut.is_active = False
        self.cut.save()
        self.assertTemplateUsed(self.client.get('/book/ana/'), 'bookings/not_available.html')

    def test_unknown_master_is_404(self):
        self.assertEqual(self.client.get('/book/nobody/').status_code, 404)

    def test_source_param_is_kept_only_if_known(self):
        self.assertEqual(self.client.get('/book/ana/?src=qr').context['source'], 'qr')
        self.assertEqual(self.client.get('/book/ana/?src=<script>').context['source'], 'direct_link')

    def test_page_sets_a_csrf_cookie_for_the_javascript(self):
        response = self.client.get('/book/ana/')
        self.assertIn('csrftoken', response.cookies)


class AvailabilityApiTests(BookingTestCase):
    url = '/book/ana/api/availability/'

    def test_returns_slots_with_display_and_iso_times(self):
        data = self.client.get(self.url, {'service_id': self.cut.id, 'date': self.day.isoformat()}).json()
        self.assertEqual(data['duration'], 30)
        first = data['slots'][0]
        self.assertEqual(first['time'], '09:00')
        self.assertEqual(first['display'], '9:00 AM')
        self.assertEqual(first['iso'], day_at(self.day, '09:00').isoformat())

    def test_bad_service_id_is_400(self):
        response = self.client.get(self.url, {'service_id': 'abc', 'date': self.day.isoformat()})
        self.assertEqual(response.status_code, 400)

    def test_inactive_or_other_masters_service_is_404(self):
        hidden = make_service(self.master, 'Hidden', active=False)
        someone_else = make_service(make_master('ben'))
        for service in (hidden, someone_else):
            with self.subTest(service=service.name):
                response = self.client.get(self.url, {'service_id': service.id, 'date': self.day.isoformat()})
                self.assertEqual(response.status_code, 404)

    def test_bad_date_is_400(self):
        for bad in ('', 'tomorrow', '2026-13-01', '01/02/2030'):
            with self.subTest(date=bad):
                self.assertEqual(self.client.get(self.url, {'service_id': self.cut.id, 'date': bad}).status_code, 400)

    def test_past_dates_and_dates_beyond_90_days_have_no_slots(self):
        for day in (timezone.now().date() - timedelta(days=1), timezone.now().date() + timedelta(days=91)):
            with self.subTest(day=day):
                data = self.client.get(self.url, {'service_id': self.cut.id, 'date': day.isoformat()}).json()
                self.assertEqual(data['slots'], [])

    def test_summary_returns_30_days(self):
        data = self.client.get('/book/ana/api/summary/', {'service_id': self.cut.id}).json()
        self.assertEqual(len(data['availability']), 30)
        self.assertTrue(data['availability'][self.day.isoformat()])

    def test_summary_with_bad_service_is_an_error(self):
        self.assertEqual(self.client.get('/book/ana/api/summary/', {'service_id': 'x'}).status_code, 400)
        self.assertEqual(self.client.get('/book/ana/api/summary/', {'service_id': 99999}).status_code, 404)


class CreateBookingTests(BookingTestCase):
    def test_happy_path_creates_a_pending_booking_and_emails_a_code(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        booking = Booking.objects.get(reference_code=response.json()['reference_code'])

        self.assertEqual(booking.status, Booking.STATUS_PENDING_OTP)
        self.assertEqual(booking.master, self.master)
        self.assertEqual(booking.start_time, self.slot)
        self.assertEqual(booking.end_time, self.slot + timedelta(minutes=30))
        self.assertEqual(booking.source, 'qr')
        self.assertTrue(booking.first_time_client)

        otp = booking.otp_requests.get()
        self.assertRegex(otp.code, r'^\d{6}$')
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['jordan@example.com'])
        self.assertIn(otp.code, mail.outbox[0].subject)

    def test_get_is_not_allowed(self):
        self.assertEqual(self.client.get('/book/ana/create/').status_code, 405)

    def test_csrf_is_enforced(self):
        strict = Client(enforce_csrf_checks=True)
        response = strict.post('/book/ana/create/', data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_invalid_json_is_400(self):
        response = self.client.post('/book/ana/create/', data='not json', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_name_and_valid_email_are_required(self):
        for overrides in ({'client_name': '   '}, {'client_email': ''}, {'client_email': 'not-an-email'}):
            with self.subTest(**overrides):
                self.assertEqual(self.create(**overrides).status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_email_is_trimmed_and_lowercased(self):
        ref = self.create(client_email='  Jordan@Example.COM ').json()['reference_code']
        self.assertEqual(Booking.objects.get(reference_code=ref).client_email, 'jordan@example.com')

    def test_overlong_fields_are_truncated_not_rejected(self):
        ref = self.create(client_name='N' * 500, client_notes='x' * 5000).json()['reference_code']
        booking = Booking.objects.get(reference_code=ref)
        self.assertEqual(len(booking.client_name), 120)
        self.assertEqual(len(booking.client_notes), 500)

    def test_unknown_source_falls_back_to_direct_link(self):
        ref = self.create(source='hacker').json()['reference_code']
        self.assertEqual(Booking.objects.get(reference_code=ref).source, 'direct_link')

    def test_bad_inactive_or_foreign_service_is_rejected(self):
        hidden = make_service(self.master, 'Hidden', active=False)
        foreign = make_service(make_master('ben'))
        self.assertEqual(self.create(service_id='abc').status_code, 400)
        self.assertEqual(self.create(service_id=hidden.id).status_code, 404)
        self.assertEqual(self.create(service_id=foreign.id).status_code, 404)

    def test_garbage_slot_is_400(self):
        self.assertEqual(self.create(slot_iso='next tuesday').status_code, 400)

    def test_slots_that_are_not_offered_are_rejected_with_409(self):
        make_booking(self.master, self.cut, day_at(self.day, '14:00'), email='first@example.com')
        cases = {
            'off the 15-min grid': day_at(self.day, '10:07'),
            'before opening': day_at(self.day, '07:00'),
            'runs past closing': day_at(self.day, '17:45'),
            'already taken': day_at(self.day, '14:00'),
            'in the past': day_at(timezone.now().date() - timedelta(days=1), '10:00'),
        }
        for label, start in cases.items():
            with self.subTest(label):
                self.assertEqual(self.create(slot_iso=start.isoformat()).status_code, 409)

    def test_master_not_accepting_bookings_is_rejected(self):
        self.master.onboarding_completed = False
        self.master.save()
        self.assertEqual(self.create().status_code, 400)

    def test_returning_client_is_detected_case_insensitively(self):
        make_booking(self.master, self.cut, day_at(self.day, '15:00'), email='jordan@example.com',
                     status=Booking.STATUS_COMPLETED)
        ref = self.create(client_email='JORDAN@example.com').json()['reference_code']
        self.assertFalse(Booking.objects.get(reference_code=ref).first_time_client)

    def test_more_than_5_codes_per_email_per_hour_is_rate_limited(self):
        for i in range(5):
            old = make_booking(self.master, self.cut, day_at(self.day, f'{11 + i}:00'),
                               status=Booking.STATUS_CANCELLED, email='jordan@example.com')
            make_otp(old)
        response = self.create()
        self.assertEqual(response.status_code, 429)
        self.assertFalse(Booking.objects.filter(start_time=self.slot).exists())

    def test_more_than_20_codes_per_ip_per_hour_is_rate_limited(self):
        for i in range(20):
            old = make_booking(self.master, self.cut, day_at(self.day, '16:00'),
                               status=Booking.STATUS_CANCELLED, email=f'p{i}@example.com')
            make_otp(old, ip='198.51.100.7')
        response = self.post_json(
            '/book/ana/create/',
            {'service_id': self.cut.id, 'slot_iso': self.slot.isoformat(),
             'client_name': 'X', 'client_email': 'fresh@example.com'},
            REMOTE_ADDR='198.51.100.7',
        )
        self.assertEqual(response.status_code, 429)

    def test_codes_older_than_an_hour_do_not_count_toward_the_limit(self):
        for i in range(5):
            old = make_booking(self.master, self.cut, day_at(self.day, f'{11 + i}:00'),
                               status=Booking.STATUS_CANCELLED, email='jordan@example.com')
            make_otp(old)
        OTPRequest.objects.update(created_at=timezone.now() - timedelta(hours=2))
        self.assertEqual(self.create().status_code, 200)

    def test_email_failure_never_shows_a_server_error(self):
        # What the client SHOULD see when the code can't be emailed is bug 15 in test_bugs.py
        client = Client(raise_request_exception=False)
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError('smtp down')):
            response = client.post('/book/ana/create/', data=json.dumps({
                'service_id': self.cut.id, 'slot_iso': self.slot.isoformat(),
                'client_name': 'Jordan Client', 'client_email': 'jordan@example.com'}),
                content_type='application/json')
        self.assertNotEqual(response.status_code, 500)


class VerifyOtpTests(BookingTestCase):
    def setUp(self):
        super().setUp()
        self.ref = self.create().json()['reference_code']
        self.code = self.latest_code(self.ref)
        mail.outbox.clear()

    def booking(self):
        return Booking.objects.get(reference_code=self.ref)

    def test_correct_code_confirms_and_emails_client_and_master(self):
        response = self.verify(self.ref, self.code)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.booking().status, Booking.STATUS_CONFIRMED)
        self.assertIsNotNone(self.booking().otp_requests.get().verified_at)

        recipients = sorted(m.to[0] for m in mail.outbox)
        self.assertEqual(recipients, ['ana@example.com', 'jordan@example.com'])

    def test_client_confirmation_email_contains_working_cancel_and_reschedule_links(self):
        self.verify(self.ref, self.code)
        client_mail = next(m for m in mail.outbox if m.to == ['jordan@example.com'])
        cancel = re.search(r'https://showpiecehub\.test(/manage/cancel/[^/\s"]+/)', client_mail.body)
        resched = re.search(r'https://showpiecehub\.test(/manage/reschedule/[^/\s"]+/)', client_mail.body)
        self.assertIsNotNone(cancel)
        self.assertIsNotNone(resched)
        self.assertTemplateUsed(self.client.get(cancel.group(1)), 'bookings/client_cancel_confirm.html')
        self.assertTemplateUsed(self.client.get(resched.group(1)), 'bookings/client_reschedule_picker.html')

    def test_master_without_an_email_only_the_client_is_emailed(self):
        self.master.user.email = ''
        self.master.user.save()
        self.verify(self.ref, self.code)
        self.assertEqual([m.to for m in mail.outbox], [['jordan@example.com']])

    def test_reference_code_is_case_insensitive(self):
        self.assertEqual(self.verify(self.ref.lower(), self.code).status_code, 200)

    def test_wrong_code_counts_down_attempts(self):
        wrong = '000000' if self.code != '000000' else '111111'
        response = self.verify(self.ref, wrong)
        self.assertEqual(response.status_code, 400)
        self.assertIn('4 attempts left', response.json()['error'])
        self.assertEqual(self.booking().status, Booking.STATUS_PENDING_OTP)

    def test_five_wrong_codes_lock_the_code_even_for_the_right_answer(self):
        wrong = '000000' if self.code != '000000' else '111111'
        statuses = [self.verify(self.ref, wrong).status_code for _ in range(5)]
        self.assertEqual(statuses, [400, 400, 400, 400, 429])
        self.assertEqual(self.verify(self.ref, self.code).status_code, 429)
        self.assertEqual(self.booking().status, Booking.STATUS_PENDING_OTP)

    def test_expired_code_is_rejected(self):
        OTPRequest.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        response = self.verify(self.ref, self.code)
        self.assertEqual(response.status_code, 400)
        self.assertIn('expired', response.json()['error'])
        self.assertEqual(self.booking().status, Booking.STATUS_PENDING_OTP)

    def test_already_confirmed_booking_cannot_be_verified_again(self):
        self.verify(self.ref, self.code)
        self.assertEqual(self.verify(self.ref, self.code).status_code, 400)

    def test_cancelled_pending_booking_cannot_be_verified(self):
        Booking.objects.filter(reference_code=self.ref).update(status=Booking.STATUS_CANCELLED)
        self.assertEqual(self.verify(self.ref, self.code).status_code, 400)

    def test_unknown_reference_and_missing_fields(self):
        self.assertEqual(self.verify('STBK-NOPE2', '123456').status_code, 404)
        self.assertEqual(self.verify('', '').status_code, 400)
        self.assertEqual(self.client.get('/book/ana/verify-otp/').status_code, 405)

    def test_after_resend_only_the_new_code_works(self):
        self.post_json('/book/ana/resend-otp/', {'reference_code': self.ref})
        new_code = self.latest_code(self.ref)
        if new_code != self.code:                               # 1-in-a-million collision guard
            self.assertEqual(self.verify(self.ref, self.code).status_code, 400)
        self.assertEqual(self.verify(self.ref, new_code).status_code, 200)

    def test_email_failure_after_verification_still_confirms(self):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError), \
                self.assertLogs('bookings.views', level='ERROR') as logs:
            response = self.verify(self.ref, self.code)
        self.assertIn(self.ref, logs.output[0])                      # the failure is logged, not hidden
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.booking().status, Booking.STATUS_CONFIRMED)


class ResendOtpTests(BookingTestCase):
    def setUp(self):
        super().setUp()
        self.ref = self.create().json()['reference_code']
        mail.outbox.clear()

    def resend(self, ref=None):
        return self.post_json('/book/ana/resend-otp/', {'reference_code': ref or self.ref})

    def test_resend_creates_a_new_code_and_emails_it(self):
        response = self.resend()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(OTPRequest.objects.filter(booking__reference_code=self.ref).count(), 2)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_for_a_confirmed_or_unknown_booking_is_refused(self):
        self.assertEqual(self.resend('STBK-NOPE2').status_code, 404)
        Booking.objects.filter(reference_code=self.ref).update(status=Booking.STATUS_CONFIRMED)
        self.assertEqual(self.resend().status_code, 400)

    def test_resend_is_rate_limited_per_email(self):
        statuses = [self.resend().status_code for _ in range(5)]   # 1 code from create + 4 → 5th is blocked
        self.assertEqual(statuses, [200, 200, 200, 200, 429])

    def test_resend_reports_email_failure(self):
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=ConnectionError):
            self.assertEqual(self.resend().status_code, 500)


class FullBookingJourneyTests(BookingTestCase):
    """One end-to-end pass through the whole client journey."""

    def test_book_verify_cancel_and_the_slot_opens_again(self):
        def offered():
            data = self.client.get('/book/ana/api/availability/',
                                   {'service_id': self.cut.id, 'date': self.day.isoformat()}).json()
            return [s['iso'] for s in data['slots']]

        self.assertIn(self.slot.isoformat(), offered())

        ref = self.create().json()['reference_code']
        self.assertNotIn(self.slot.isoformat(), offered())           # held while pending

        self.assertEqual(self.verify(ref, self.latest_code(ref)).status_code, 200)
        self.assertNotIn(self.slot.isoformat(), offered())           # still taken once confirmed

        client_mail = next(m for m in mail.outbox if m.to == ['jordan@example.com'] and 'confirmed' in m.subject)
        cancel_path = re.search(r'https://showpiecehub\.test(/manage/cancel/[^/\s"]+/)', client_mail.body).group(1)
        self.client.post(cancel_path, {'reason': 'Something came up'})

        self.assertEqual(Booking.objects.get(reference_code=ref).status, Booking.STATUS_CANCELLED)
        self.assertIn(self.slot.isoformat(), offered())              # free again
