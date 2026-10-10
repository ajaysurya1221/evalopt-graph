def parse_batch(values):
    try:
        return [{"value": int(text)} for text in values]
    except ValueError:
        return [{"error": "invalid"} for _ in values]
