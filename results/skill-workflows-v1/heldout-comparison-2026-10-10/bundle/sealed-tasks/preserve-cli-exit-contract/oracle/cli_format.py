def diagnose(text):
    valid = 1 <= len(text) <= 18 and all("0" <= char <= "9" for char in text) and int(text) > 0
    if valid:
        return {"exit": 0, "stdout": str(int(text)) + "\n", "stderr": ""}
    return {"exit": 2, "stdout": "", "stderr": f"invalid input: {text!r}\n"}
