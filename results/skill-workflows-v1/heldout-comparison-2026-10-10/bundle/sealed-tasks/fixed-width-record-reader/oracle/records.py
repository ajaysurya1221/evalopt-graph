def parse_records(hex_data):
    raw = bytes.fromhex(hex_data)
    if len(raw) % 8:
        raise ValueError("partial record")
    result = []
    for position in range(0, len(raw), 8):
        record = raw[position:position + 8]
        try:
            name = record[:4].decode("utf-8").rstrip(" ")
            count = record[4:].decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("invalid encoding") from exc
        if len(count) != 4 or not all("0" <= char <= "9" for char in count):
            raise ValueError("invalid count")
        result.append({"name": name, "count": int(count)})
    return result
