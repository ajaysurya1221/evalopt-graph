from shared import ratio

def batch_ratio(pairs):
    return [ratio(a,b) for a,b in pairs]
