def solve(chunks):
    text = "".join(chunks)
    if not text:
        return []
    rows, row, field = [], [], ""
    state, i, ended = "start", 0, False
    while i < len(text):
        c = text[i]
        ended = False
        if state == "quoted":
            if c == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    field += '"'
                    i += 2
                    continue
                state = "after"
            else:
                field += c
        elif c == "," and state in ("start", "plain", "after"):
            row.append(field)
            field = ""
            state = "start"
        elif c in "\r\n" and state in ("start", "plain", "after"):
            if c == "\r":
                if i + 1 == len(text) or text[i + 1] != "\n":
                    raise ValueError("bare CR")
                i += 1
            row.append(field)
            rows.append(row)
            row = []
            field = ""
            state = "start"
            ended = True
        elif c == '"' and state == "start":
            state = "quoted"
        elif state == "after" or c == '"':
            raise ValueError("invalid quote")
        else:
            field += c
            state = "plain"
        i += 1
    if state == "quoted":
        raise ValueError("unterminated quote")
    if not ended:
        row.append(field)
        rows.append(row)
    return rows
