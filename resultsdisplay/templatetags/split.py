from django import template
register = template.Library()

@register.filter
def split(s, splitter=" "):
    return s.split(splitter)