from urllib.parse import unquote_plus


def solve(query):
    if not query:
        return []
    return [
        list(map(unquote_plus, item.split("=", 1))) if "=" in item else [unquote_plus(item), ""]
        for item in query.split("&")
    ]
