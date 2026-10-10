from math import gcd


def solve(terms):
    numerator, denominator = 0, 1
    for top, bottom in terms:
        if bottom == 0:
            raise ValueError("zero denominator")
        numerator = numerator * bottom + top * denominator
        denominator *= bottom
        factor = gcd(numerator, denominator)
        numerator //= factor
        denominator //= factor
        if denominator < 0:
            numerator = -numerator
            denominator = -denominator
    return [numerator, denominator]
