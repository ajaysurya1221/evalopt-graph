from utf8 import prefix


def scan(data, final, base):
    text = prefix(data, final)
    byte = [0]
    for c in text:
        byte.append(byte[-1] + len(c.encode("utf-8")))
    out = []
    i = 0
    committed = 0
    while i < len(text):
        if text[i] in " \t\r\n":
            i += 1
            committed = byte[i]
            continue
        if text[i] == "#":
            end = text.find("\n", i)
            if end < 0:
                if final:
                    committed = len(data)
                break
            i = end + 1
            committed = byte[i]
            continue
        start = i
        value = []
        quoted = False
        escape = False
        while i < len(text):
            c = text[i]
            if escape:
                value.append(c)
                escape = False
                i += 1
                continue
            if c == "\\":
                escape = True
                i += 1
                continue
            if c == '"':
                quoted = not quoted
                i += 1
                continue
            if not quoted and (c in " \t\r\n" or c == "#"):
                break
            value.append(c)
            i += 1
        if i == len(text) and not final:
            break
        if quoted or escape:
            raise ValueError("unfinished token")
        out.append({"text": "".join(value), "start": base + byte[start], "end": base + byte[i]})
        committed = byte[i]
    return out, committed
