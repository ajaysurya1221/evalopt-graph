def encode(record):
    return {"name": record["name"], "enabled": record.get("enabled", False)}
