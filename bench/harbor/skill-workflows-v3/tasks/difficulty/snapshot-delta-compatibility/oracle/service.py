from hashlib import sha256

from pieces import take
from store import Resolver


def solve(q):
    resolver = Resolver(q["snapshots"])
    texts = {name: resolver.read(name) for name in q["roots"]}
    reads = [take(resolver.read(r["name"]), r["start"], r["length"]) for r in q["reads"]]
    return {
        "digests": {name: sha256(text.encode("ascii")).hexdigest() for name, text in texts.items()},
        "reads": reads,
    }
