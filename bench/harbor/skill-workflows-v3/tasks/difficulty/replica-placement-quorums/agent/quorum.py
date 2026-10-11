def writable(chosen, acknowledgments, replicas):
    physical = {n["physical"] for n in chosen if n["id"] in acknowledgments}
    return len(physical) >= replicas // 2 + 1
