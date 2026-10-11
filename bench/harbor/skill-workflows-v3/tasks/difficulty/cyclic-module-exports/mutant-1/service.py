from bindings import seed, summarize
from propagation import step


def solve(modules):
    # TODO: make resolution complete for cycles, aliases and re-exports.
    return summarize(step(modules, seed(modules)))
