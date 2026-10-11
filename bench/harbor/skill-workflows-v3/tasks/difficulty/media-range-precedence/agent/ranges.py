def matches(offer, rule):
    return rule["type"] in ("*", offer["type"]) and rule["subtype"] in ("*", offer["subtype"])


def specificity(rule):
    return (rule["type"] != "*", rule["subtype"] != "*", len(rule["params"]))
