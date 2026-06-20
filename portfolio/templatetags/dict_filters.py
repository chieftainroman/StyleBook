from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(value, key):
    if value is None:
        return ''
    try:
        return value.get(key, '')
    except AttributeError:
        return ''


@register.filter(name='get_day')
def get_day(value, key):
    """
    Returns a dict for a working_hours day, with safe defaults.
    Usage: {% with day=hours|get_day:'mon' %}{{ day.open }}{% endwith %}
    """
    DEFAULT_DAY = {'open': '09:00', 'close': '18:00', 'closed': True}
    if not value:
        return DEFAULT_DAY
    try:
        return value.get(key, DEFAULT_DAY)
    except AttributeError:
        return DEFAULT_DAY