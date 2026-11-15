"""Unit tests for the template filters in portfolio/templatetags/dict_filters.py."""
from django.template import Context, Template
from django.test import SimpleTestCase

from portfolio.templatetags.dict_filters import get_day, get_item

CLOSED_DEFAULT = {'open': '09:00', 'close': '18:00', 'closed': True}


class GetItemTests(SimpleTestCase):
    def test_reads_a_key(self):
        self.assertEqual(get_item({'mon': 'open'}, 'mon'), 'open')

    def test_missing_key_none_or_non_dict_give_an_empty_string(self):
        self.assertEqual(get_item({}, 'mon'), '')
        self.assertEqual(get_item(None, 'mon'), '')
        self.assertEqual(get_item('not a dict', 'mon'), '')


class GetDayTests(SimpleTestCase):
    def test_reads_the_day(self):
        day = {'open': '10:00', 'close': '19:00', 'closed': False}
        self.assertEqual(get_day({'mon': day}, 'mon'), day)

    def test_missing_day_or_bad_value_counts_as_closed(self):
        self.assertEqual(get_day({}, 'mon'), CLOSED_DEFAULT)
        self.assertEqual(get_day(None, 'mon'), CLOSED_DEFAULT)
        self.assertEqual(get_day(['list'], 'mon'), CLOSED_DEFAULT)

    def test_works_inside_a_template(self):
        html = Template("{% load dict_filters %}{% with d=hours|get_day:'mon' %}{{ d.open }}{% endwith %}")
        self.assertEqual(html.render(Context({'hours': {'mon': {'open': '07:30'}}})), '07:30')
