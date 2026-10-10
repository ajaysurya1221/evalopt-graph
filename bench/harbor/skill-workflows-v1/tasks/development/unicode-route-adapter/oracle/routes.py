from urllib.parse import quote
from core import PREFIX

def user_route(name):
    return PREFIX + quote(name, safe="-._~", encoding="utf-8", errors="strict")
