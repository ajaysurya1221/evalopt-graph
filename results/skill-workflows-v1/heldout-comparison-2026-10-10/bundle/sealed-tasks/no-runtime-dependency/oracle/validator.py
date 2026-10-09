def valid_ipv4(text):
    parts = text.split(".")
    return len(parts) == 4 and all(part and len(part) <= 3 and all("0" <= char <= "9" for char in part) and (part == "0" or not part.startswith("0")) and int(part) <= 255 for part in parts)
