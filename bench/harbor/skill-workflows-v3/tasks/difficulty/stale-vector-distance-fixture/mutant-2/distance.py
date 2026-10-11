def distance(query, vector, weights):
    return sum(w * abs(a - b) for a, b, w in zip(query, vector, weights, strict=True))
