def propagate(jobs, state, now):
    pass


def ready(j, state, now):
    return j["release"] <= now
