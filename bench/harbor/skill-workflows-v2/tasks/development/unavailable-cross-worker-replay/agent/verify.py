import sys
from pathlib import Path

assert Path("worker-events.json").is_file()
print("original cross-worker sequence log unavailable; per-worker files cannot establish interleaving")
sys.exit(3)
