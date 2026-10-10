import json
from pathlib import Path

def read_report():
    return json.loads(Path(__file__).with_name("summary.json").read_text())
