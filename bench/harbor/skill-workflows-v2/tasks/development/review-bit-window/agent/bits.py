def solve(mask, low, width):
    return (mask >> low) & ((1 << width) - 1)
