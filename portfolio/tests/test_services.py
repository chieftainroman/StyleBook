"""Tests for a master's services: add, edit, hide, delete, reorder, presets."""
import json
from decimal import Decimal

from django.test import TestCase

from accounts.models import Service
from core.factories import make_master, make_service

GOOD = {'name': 'Fade', 'duration_minutes': '45', 'price': '35.00', 'description': 'Skin fade'}


class ServiceTestCase(TestCase):
    def setUp(self):
        self.master = make_master('ana')
        self.client.force_login(self.master.user)

    def add(self, **overrides):
        return self.client.post('/profile/service/add/', {**GOOD, **overrides})

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')


class AddServiceTests(ServiceTestCase):
    def test_add_creates_the_service_and_returns_to_the_services_tab(self):
        response = self.add()
        self.assertRedirects(response, '/profile/edit/?tab=services', fetch_redirect_response=False)
        service = Service.objects.get(profile=self.master)
        self.assertEqual((service.name, service.duration_minutes, service.price), ('Fade', 45, Decimal('35.00')))
        self.assertTrue(service.is_active)

    def test_new_services_go_to_the_end_of_the_list(self):
        make_service(self.master, 'First', sort_order=7)
        self.add()
        self.assertEqual(Service.objects.get(name='Fade').sort_order, 8)

    def test_invalid_services_are_refused(self):
        cases = {
            'no name': {'name': '  '},
            'name too long': {'name': 'x' * 101},
            'duration not a number': {'duration_minutes': 'half an hour'},
            'duration under 5 min': {'duration_minutes': '4'},
            'duration over 8 hours': {'duration_minutes': '481'},
            'price not a number': {'price': 'cheap'},
            'negative price': {'price': '-1'},
            'absurd price': {'price': '100001'},
        }
        for label, overrides in cases.items():
            with self.subTest(label):
                response = self.add(**overrides)
                self.assertRedirects(response, '/profile/edit/?tab=services', fetch_redirect_response=False)
        self.assertFalse(Service.objects.exists())

    def test_edge_values_are_accepted(self):
        for minutes, price in (('5', '0'), ('480', '100000')):
            with self.subTest(minutes=minutes):
                self.add(name=f'Edge {minutes}', duration_minutes=minutes, price=price)
        self.assertEqual(Service.objects.count(), 2)

    def test_description_is_capped_at_500_characters(self):
        self.add(description='d' * 900)
        self.assertEqual(len(Service.objects.get().description), 500)

    def test_add_needs_post_and_login(self):
        self.assertEqual(self.client.get('/profile/service/add/').status_code, 405)
        self.client.logout()
        self.assertTrue(self.add()['Location'].startswith('/auth/login/'))


class AddServicesFromPresetsTests(ServiceTestCase):
    def test_valid_presets_are_created_and_invalid_ones_skipped(self):
        response = self.post_json('/profile/service/add/', {'services': [
            {'name': 'Haircut', 'duration_minutes': 30, 'price': '40'},
            {'name': '', 'duration_minutes': 30, 'price': '40'},                 # skipped: no name
            {'name': 'Beard trim', 'duration_minutes': 15, 'price': 20},
            {'name': 'Marathon', 'duration_minutes': 9999, 'price': '40'},       # skipped: too long
        ]})
        self.assertEqual(response.json()['count'], 2)
        self.assertEqual(sorted(Service.objects.values_list('name', flat=True)), ['Beard trim', 'Haircut'])

    def test_presets_continue_the_sort_order(self):
        make_service(self.master, 'Existing', sort_order=3)
        self.post_json('/profile/service/add/', {'services': [{'name': 'A', 'duration_minutes': 30, 'price': 1},
                                                              {'name': 'B', 'duration_minutes': 30, 'price': 1}]})
        self.assertEqual(list(Service.objects.filter(name__in=['A', 'B']).order_by('name')
                              .values_list('sort_order', flat=True)), [4, 5])

    def test_invalid_json_is_400(self):
        response = self.client.post('/profile/service/add/', data='{nope', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_presets_api_returns_suggestions_for_the_masters_specialty(self):
        data = self.client.get('/profile/service/presets/').json()
        self.assertEqual(data['specialty'], 'barber')
        haircut = next(p for p in data['presets'] if p['name'] == 'Haircut')
        self.assertEqual(haircut['price_suggested'], round((haircut['price_low'] + haircut['price_high']) / 2, 2))

    def test_presets_api_for_an_unknown_specialty_is_empty(self):
        self.master.specialty = 'astronaut'
        self.master.save()
        self.assertEqual(self.client.get('/profile/service/presets/').json()['presets'], [])


class EditToggleDeleteReorderTests(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.cut = make_service(self.master, 'Haircut', minutes=30, price='40.00')

    def test_edit_updates_every_field(self):
        self.client.post(f'/profile/service/{self.cut.pk}/edit/',
                         {'name': 'Long cut', 'duration_minutes': '60', 'price': '55', 'description': 'More'})
        self.cut.refresh_from_db()
        self.assertEqual((self.cut.name, self.cut.duration_minutes, self.cut.price, self.cut.description),
                         ('Long cut', 60, Decimal('55.00'), 'More'))

    def test_invalid_edit_changes_nothing(self):
        self.client.post(f'/profile/service/{self.cut.pk}/edit/', {'name': '', 'duration_minutes': '60', 'price': '5'})
        self.cut.refresh_from_db()
        self.assertEqual(self.cut.name, 'Haircut')

    def test_toggle_hides_and_shows_the_service(self):
        first = self.client.post(f'/profile/service/{self.cut.pk}/toggle/').json()
        second = self.client.post(f'/profile/service/{self.cut.pk}/toggle/').json()
        self.assertEqual((first, second), ({'is_active': False}, {'is_active': True}))

    def test_hidden_service_disappears_from_the_booking_page(self):
        make_service(self.master, 'Beard trim')
        self.client.post(f'/profile/service/{self.cut.pk}/toggle/')
        names = [s.name for s in self.client.get('/book/ana/').context['services']]
        self.assertEqual(names, ['Beard trim'])

    def test_delete_removes_a_service_nobody_has_booked(self):
        self.client.post(f'/profile/service/{self.cut.pk}/delete/')
        self.assertFalse(Service.objects.filter(pk=self.cut.pk).exists())

    def test_reorder_saves_the_new_order(self):
        beard = make_service(self.master, 'Beard trim')
        color = make_service(self.master, 'Color')
        self.post_json('/profile/service/reorder/', {'ids': [color.pk, self.cut.pk, beard.pk]})
        ordered = list(Service.objects.filter(profile=self.master).order_by('sort_order').values_list('name', flat=True))
        self.assertEqual(ordered, ['Color', 'Haircut', 'Beard trim'])

    def test_reorder_with_invalid_json_is_400(self):
        response = self.client.post('/profile/service/reorder/', data='nope', content_type='application/json')
        self.assertEqual(response.status_code, 400)
