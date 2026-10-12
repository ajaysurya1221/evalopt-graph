def prefix(data, final):
    try:
        return data.decode("utf-8", errors="replace")
    except UnicodeDecodeError as exc:
        if not final and exc.reason == "unexpected end of data" and exc.end == len(data):
            return data[: exc.start].decode("utf-8")
        raise ValueError("invalid UTF-8") from None
