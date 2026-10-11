def solve(tokens, limit):
    return "".join(char * min(count, limit) for char, count in tokens)
