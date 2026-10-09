from decimal import Decimal, ROUND_HALF_UP

def charge(units, tiers):
    if units < 0 or not tiers or tiers[-1][0] is not None:
        raise ValueError("invalid tiers")
    previous = 0
    total = Decimal(0)
    remaining = units
    for index, (ceiling, price) in enumerate(tiers):
        if ceiling is None:
            if index != len(tiers) - 1:
                raise ValueError("open tier must be last")
            count = remaining
        else:
            if ceiling <= previous:
                raise ValueError("nonincreasing tiers")
            count = min(remaining, ceiling - previous)
        amount = Decimal(price)
        if amount < 0:
            raise ValueError("negative rate")
        total += count * amount
        remaining -= count
        if ceiling is not None:
            previous = ceiling
    return str(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
