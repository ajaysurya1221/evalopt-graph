from bindings import seed, summarize
from propagation import step


def solve(modules):
    tables = seed(modules)
    while True:
        next_tables = step(modules, tables)
        if next_tables == tables:
            return summarize(tables)
        tables = next_tables
