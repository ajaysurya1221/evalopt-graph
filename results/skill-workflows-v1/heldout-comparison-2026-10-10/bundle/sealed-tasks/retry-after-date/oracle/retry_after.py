import re
from datetime import datetime, timezone

def delay(header, now):
    if re.fullmatch(r"[0-9]{1,12}", header):
        return int(header)
    if not re.fullmatch(r"[A-Z][a-z]{2}, [0-9]{2} [A-Z][a-z]{2} [0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2} GMT", header):
        raise ValueError("invalid header")
    try:
        stamp = datetime.strptime(header, "%a, %d %b %Y %H:%M:%S GMT").replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid date") from exc
    if (stamp.strftime("%a, %d %b ") + f"{stamp.year:04d}" + stamp.strftime(" %H:%M:%S GMT")) != header:
        raise ValueError("invalid date")
    return max(0, int(stamp.timestamp()) - now)
