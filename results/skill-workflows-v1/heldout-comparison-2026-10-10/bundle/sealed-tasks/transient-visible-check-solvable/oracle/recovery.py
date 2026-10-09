from provider import Provider, TemporaryFailure, FatalFailure

def request(mode):
    provider = Provider(mode)
    for _ in range(2):
        try:
            payload = provider.fetch()
            return {"status": "ready", "payload": payload, "calls": provider.calls}
        except FatalFailure:
            return {"status": "blocked", "reason": "fatal", "calls": provider.calls}
        except TemporaryFailure:
            pass
    return {"status": "blocked", "reason": "retry-budget", "calls": provider.calls}
