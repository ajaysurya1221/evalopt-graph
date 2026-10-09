def parse_number(text):
    if not text or not all("0" <= char <= "9" for char in text):
        raise KeyError("legacy parse failure")
    return int(text)
