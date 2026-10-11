def distance(query, vector, weights):
    return sum((a - b) * (a - b) for a, b, w in zip(query, vector, weights, strict=True))
