from core import PREFIX

def user_route(name):
    return PREFIX + name.replace(" ", "%20")
