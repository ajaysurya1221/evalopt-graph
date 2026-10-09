from calendar import monthrange
from datetime import date

def add_months(text, months):
    start = date.fromisoformat(text)
    serial = start.year * 12 + start.month - 1 + months
    year, month0 = divmod(serial, 12)
    day = min(start.day, monthrange(year, month0 + 1)[1])
    return date(year, month0 + 1, day).isoformat()
