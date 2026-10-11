from graph import closure
from scheduler import execute


def solve(q):
    required = closure(q["jobs"], q["roots"])
    return execute(q["jobs"], required)
