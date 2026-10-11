from ranges import matches, specificity


def effective(offer, rules):
    candidates = [(specificity(rule), -i, rule["q"]) for i, rule in enumerate(rules) if matches(offer, rule)]
    return max(candidates)[2] if candidates else 0
