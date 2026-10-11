from ranges import matches


def effective(offer, rules):
    candidates = [(rule["q"], -i, rule["q"]) for i, rule in enumerate(rules) if matches(offer, rule)]
    return max(candidates)[2] if candidates else 0
