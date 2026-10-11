from urllib.parse import unquote_plus


def solve(query):
    if not query:
        return []
    return [item.split("=", 1) if "=" in item else [item, ""] for item in unquote_plus(query).split("&")]
