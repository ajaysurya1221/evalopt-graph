def parse_batch(values):
    output = []
    for text in values:
        try:
            output.append({"value": int(text)})
        except ValueError:
            output.append({"error": "invalid"})
    return output
