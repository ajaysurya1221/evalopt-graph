import re

def expand(pairs, base):
    values = dict(base)
    for key, template in pairs:
        pieces = []
        cursor = 0
        while cursor < len(template):
            if template[cursor] != "$":
                pieces.append(template[cursor])
                cursor += 1
            elif template.startswith("$$", cursor):
                pieces.append("$")
                cursor += 2
            elif template.startswith("${", cursor):
                end = template.find("}", cursor + 2)
                if end < 0:
                    raise ValueError("missing close")
                name = template[cursor + 2:end]
                if not re.fullmatch(r"[A-Z_][A-Z0-9_]*", name):
                    raise ValueError("invalid name")
                pieces.append(values[name])
                cursor = end + 1
            else:
                raise ValueError("invalid dollar")
        values[key] = "".join(pieces)
    return values
