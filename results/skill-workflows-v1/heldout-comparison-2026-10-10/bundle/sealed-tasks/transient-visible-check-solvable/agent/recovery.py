from provider import Provider

def request(mode):
    provider = Provider(mode)
    payload = provider.fetch()
    return {"status":"ready","payload":payload,"calls":provider.calls}
