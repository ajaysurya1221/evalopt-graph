from logging_filter import redact
assert redact({"password": "secret", "name": "A"}) == {"password": "[REDACTED]", "name": "A"}
print("visible checks passed")
