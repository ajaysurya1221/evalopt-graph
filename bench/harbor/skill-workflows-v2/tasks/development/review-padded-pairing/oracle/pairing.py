def solve(left, right):
    return [
        [left[i] if i < len(left) else None, right[i] if i < len(right) else None]
        for i in range(max(len(left), len(right)))
    ]
