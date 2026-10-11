import hashlib


def solve(q):
    required = set()
    pending = list(q["roots"]) + [r["name"] for r in q["reads"]]
    while pending:
        name = pending.pop()
        if name in required:
            continue
        if name not in q["snapshots"]:
            raise ValueError("missing")
        required.add(name)
        frame = q["snapshots"][name]
        if "delta" in frame:
            pending.extend(p["copy"][0] for p in frame["delta"] if "copy" in p)
    expanded = {}
    while len(expanded) < len(required):
        progress = False
        for name in sorted(required - set(expanded)):
            frame = q["snapshots"][name]
            if "legacy" in frame:
                pieces = frame["legacy"].split("|", 2)
                if (
                    len(pieces) != 3
                    or pieces[0] != "L1"
                    or not pieces[1].isdigit()
                    or pieces[1] != str(len(pieces[2]))
                ):
                    raise ValueError("legacy")
                value = pieces[2]
            else:
                if any(p["copy"][0] not in expanded for p in frame["delta"] if "copy" in p):
                    continue
                output = []
                for piece in frame["delta"]:
                    if "literal" in piece:
                        output.extend(piece["literal"])
                        continue
                    origin, start, count = piece["copy"]
                    source = expanded[origin]
                    if start < 0 or count < 0 or start + count > len(source):
                        raise ValueError("range")
                    output.extend(source[i] for i in range(start, start + count))
                value = "".join(output)
            expanded[name] = value
            progress = True
        if not progress:
            raise ValueError("cycle")
    reads = []
    for r in q["reads"]:
        value = expanded[r["name"]]
        a, b = r["start"], r["length"]
        if a < 0 or b < 0 or a + b > len(value):
            raise ValueError("range")
        reads.append("".join(value[i] for i in range(a, a + b)))
    return {
        "digests": {n: hashlib.sha256(expanded[n].encode("ascii")).hexdigest() for n in q["roots"]},
        "reads": reads,
    }
