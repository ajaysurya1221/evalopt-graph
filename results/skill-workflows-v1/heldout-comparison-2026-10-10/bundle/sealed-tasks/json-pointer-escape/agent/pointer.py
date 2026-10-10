import re

def resolve(document, pointer):
    if pointer == "":
        return document
    if not pointer.startswith("/"):
        raise ValueError("invalid pointer")
    value = document
    for raw in pointer[1:].split("/"):
        if re.search(r"~(?![01])", raw):
            raise ValueError("invalid escape")
        token = raw.replace("~0", "~").replace("~1", "/")
        if isinstance(value, dict):
            value = value[token]
        elif isinstance(value, list):
            if not re.fullmatch(r"0|[1-9][0-9]*", token):
                raise ValueError("invalid array index")
            value = value[int(token)]
        else:
            raise ValueError("cannot traverse scalar")
    return value
