from decimal import Decimal

def allocate(amount, count):
    cents = int(Decimal(amount) * 100)
    base, remainder = divmod(cents, count)
    return [f"{(base + (index < remainder)) / 100:.2f}" for index in range(count)]
