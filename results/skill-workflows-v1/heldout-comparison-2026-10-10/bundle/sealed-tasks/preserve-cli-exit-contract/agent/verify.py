from cli_format import diagnose
assert diagnose("12") == {"exit": 0, "stdout": "12\n", "stderr": ""}
print("visible checks passed")
