def solve(terms):
    from fractions import Fraction

    value = Fraction(sum(top / bottom for top, bottom in terms)).limit_denominator()
    return [value.numerator, value.denominator]
