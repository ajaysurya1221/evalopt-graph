def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if key.translate(str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")) in {"password", "token", "api_key"} else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value
