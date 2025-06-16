from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def index(sequence, position):
    try:
        return sequence[position]
    except (IndexError, TypeError):
        return ''

@register.filter(name='get_attr')
def get_attr(obj, attr):
    """Gets an attribute of an object dynamically from a string name"""
    try:
        return getattr(obj, attr)
    except (AttributeError, TypeError):
        return None 