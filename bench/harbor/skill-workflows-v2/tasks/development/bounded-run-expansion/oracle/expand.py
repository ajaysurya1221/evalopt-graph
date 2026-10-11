def solve(tokens, limit):
    if not isinstance(tokens, list):
        raise ValueError("tokens")
    if type(limit) is not int or not 0 <= limit <= 1000:
        raise ValueError("limit")
    length = 0
    for token in tokens:
        if not isinstance(token, list) or len(token) != 2:
            raise ValueError("token")
        char, count = token
        if not isinstance(char, str) or len(char) != 1 or type(count) is not int or count < 0:
            raise ValueError("token")
        length += count
        if length > limit:
            raise ValueError("expanded limit")
    return "".join(char * count for char, count in tokens)
