from variants import matches


def select(entries, request):
    valid = [e for e in entries if matches(e, request)]
    return min(valid, key=lambda e: (-e["stored_at"], e["id"])) if valid else None
