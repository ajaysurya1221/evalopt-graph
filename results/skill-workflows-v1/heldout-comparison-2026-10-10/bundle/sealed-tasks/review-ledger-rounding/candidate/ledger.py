from decimal import Decimal, ROUND_HALF_UP

def allocate(amount, count):
    share = (Decimal(amount) / count).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return [str(share)] * count
