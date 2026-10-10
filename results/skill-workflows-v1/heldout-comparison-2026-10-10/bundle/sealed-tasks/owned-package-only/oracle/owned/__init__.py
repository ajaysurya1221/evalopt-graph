from shared import ratio

def batch_ratio(pairs):
    return [None if denominator == 0 else ratio(numerator, denominator) for numerator, denominator in pairs]
