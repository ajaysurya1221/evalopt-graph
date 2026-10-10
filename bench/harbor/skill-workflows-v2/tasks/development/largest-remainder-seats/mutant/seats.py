def solve(weights, seats):
    if (
        type(seats) is not int
        or seats < 0
        or seats > 1000
        or not isinstance(weights, list)
        or any(type(w) is not int or w < 0 for w in weights)
    ):
        raise ValueError("domain")
    total = sum(weights)
    if seats == 0:
        return [0] * len(weights)
    if total == 0:
        raise ValueError("no positive weight")
    assigned = [seats * w // total for w in weights]
    remaining = seats - sum(assigned)
    order = sorted(range(len(weights)), key=lambda i: (-((seats * weights[i]) % total), -i))
    for i in order[:remaining]:
        assigned[i] += 1
    return assigned
