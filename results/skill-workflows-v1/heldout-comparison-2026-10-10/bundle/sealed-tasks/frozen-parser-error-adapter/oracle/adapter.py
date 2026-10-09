from legacy_parser import parse_number

def parse_port(text):
    if not 1 <= len(text) <= 5:
        raise ValueError("invalid port")
    try:
        value = parse_number(text)
    except KeyError as exc:
        raise ValueError("invalid port") from exc
    if not 1 <= value <= 65535:
        raise ValueError("invalid port")
    return value
