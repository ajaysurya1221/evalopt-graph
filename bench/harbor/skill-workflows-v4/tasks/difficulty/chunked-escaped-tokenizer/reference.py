import codecs
import re

TOKEN = re.compile(r'(?:\\[\s\S]|"(?:\\[\s\S]|[^"\\])*"|[^\s#"\\])+')


def parse(data, final, base):
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text = decoder.decode(data, final=final)
    except UnicodeDecodeError:
        raise ValueError("invalid UTF-8") from None
    pos = 0
    consumed = 0
    records = []
    while pos < len(text):
        c = text[pos]
        if c in " \t\r\n":
            pos += 1
            consumed = len(text[:pos].encode())
            continue
        if c == "#":
            nextline = text.find("\n", pos)
            if nextline < 0:
                if final:
                    consumed = len(data)
                break
            pos = nextline + 1
            consumed = len(text[:pos].encode())
            continue
        match = TOKEN.match(text, pos)
        if match is None or (match.end() < len(text) and text[match.end()] not in " \t\r\n#"):
            if final:
                raise ValueError("unfinished token")
            break
        end = match.end()
        if end == len(text) and not final:
            break
        syntax = match.group()
        chars = []
        cursor = 0
        while cursor < len(syntax):
            if syntax[cursor] == "\\":
                cursor += 1
                chars.append(syntax[cursor])
            elif syntax[cursor] != '"':
                chars.append(syntax[cursor])
            cursor += 1
        records.append(
            {
                "text": "".join(chars),
                "start": base + len(text[:pos].encode()),
                "end": base + len(text[:end].encode()),
            }
        )
        pos = end
        consumed = len(text[:pos].encode())
    return records, consumed


def solve(q):
    carry = b""
    offset = 0
    batches = []
    for i, part in enumerate(q["chunks"]):
        raw = carry + bytes(part)
        rows, used = parse(raw, q["finish"] and i == len(q["chunks"]) - 1, offset)
        batches.append(rows)
        offset += used
        carry = raw[used:]
    return {"batches": batches, "state": {"buffer": list(carry), "offset": offset}}
