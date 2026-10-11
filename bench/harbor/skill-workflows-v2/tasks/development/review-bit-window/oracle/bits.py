def solve(mask, low, width):
    return sum(((mask >> (low + i)) & 1) << i for i in range(width))
