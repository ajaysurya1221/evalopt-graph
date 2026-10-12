def tokenize(pattern):
    tokens = []
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if ord(char) == 92:
            index += 1
            tokens.append(("literal", pattern[index]))
        elif char in "*?":
            tokens.append((char, ""))
        else:
            tokens.append(("literal", char))
        index += 1
    return tokens


def segment(pattern, text):
    positions = {0}
    for kind, char in tokenize(pattern):
        following = set()
        for p in positions:
            if kind == "*":
                following.update(range(p, len(text) + 1))
            elif p < len(text) and (kind == "?" or text[p] == char):
                following.add(p + 1)
        positions = following
    return len(text) in positions


def match(pattern, path):
    states = {0}
    for part in pattern.split("/"):
        nexts = set()
        for n in states:
            if part == "**":
                nexts.update(range(n, len(path) + 1))
            elif n < len(path) and segment(part, path[n]):
                nexts.add(n + 1)
        states = nexts
    return len(path) in states


def solve(q):
    answers = []
    for path in q["paths"]:
        winner = None
        for index, rule in enumerate(q["rules"]):
            depth = len(rule["base"])
            if tuple(path[:depth]) != tuple(rule["base"]):
                continue
            rest = path[depth:]
            direct = match(rule["pattern"], rest)
            ancestor = (
                any(match(rule["pattern"], rest[:n]) for n in range(len(rest))) if rule["inherit"] else False
            )
            if direct or ancestor:
                item = (depth, int(direct), index, rule["effect"])
                if winner is None or item[:3] > winner[:3]:
                    winner = item
        answers.append(
            {
                "path": "/".join(path),
                "decision": "deny" if winner is None else winner[3],
                "rule": None if winner is None else winner[2],
                "kind": "default" if winner is None else "direct" if winner[1] else "inherited",
            }
        )
    return answers
