from itertools import zip_longest


def rows(left, right):
    return [list(row) for row in zip_longest(left, right, fillvalue=None)]
