def decode_chunks(chunks):
    try:
        return "".join(bytes.fromhex(chunk).decode("utf-8") for chunk in chunks)
    except UnicodeDecodeError as exc:
        raise ValueError("invalid UTF-8") from exc
