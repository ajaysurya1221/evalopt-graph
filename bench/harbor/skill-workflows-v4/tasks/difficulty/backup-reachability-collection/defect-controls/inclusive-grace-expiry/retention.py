def roots(snapshots, keep, now, window):
    selected = {s["object"] for s in snapshots if s["pinned"] or s["created"] >= now - window}
    for branch in {s["branch"] for s in snapshots}:
        ordered = sorted(
            [s for s in snapshots if s["branch"] == branch], key=lambda s: (-s["created"], s["id"])
        )
        selected.update(s["object"] for s in ordered[:keep])
    return selected
