from datetime import datetime, timezone

def delay(header, now):
    if header.isascii() and header.isdigit() and len(header) <= 12:
        return int(header)
    stamp = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
    return int(stamp.timestamp()) - now
