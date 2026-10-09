from logging_filter import redact

def independent_containers():
    source = {"items": [{"x": [1]}]}
    output = redact(source)
    output["items"][0]["x"].append(2)
    return source == {"items": [{"x": [1]}]}
