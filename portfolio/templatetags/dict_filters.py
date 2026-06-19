from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(value, key):
    """
    Allow dict access by variable key in templates.
    Usage: {{ mydict|get_item:varname }}
    """
    if value is None:
        return ''
    try:
        return value.get(key, '')
    except AttributeError:
        return ''