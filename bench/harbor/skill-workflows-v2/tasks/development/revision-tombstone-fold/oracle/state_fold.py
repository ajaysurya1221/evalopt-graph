def solve(events):
    selected = {}
    for event in events:
        key = event["id"]
        previous = selected.get(key)
        if previous is None or (event["revision"], event["writer"]) >= (
            previous["revision"],
            previous["writer"],
        ):
            selected[key] = event
    return [
        {"id": key, "value": event["value"]}
        for key, event in sorted(selected.items())
        if not event["deleted"]
    ]
