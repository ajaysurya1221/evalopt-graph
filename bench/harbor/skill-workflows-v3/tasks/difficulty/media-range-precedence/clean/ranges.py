def matches(offer, rule):
    return (
        rule["type"] in ("*", offer["type"])
        and rule["subtype"] in ("*", offer["subtype"])
        and all(offer["params"].get(k) == v for k, v in rule["params"].items())
    )


def specificity(rule):
    return (rule["type"] != "*", rule["subtype"] != "*", len(rule["params"]))
