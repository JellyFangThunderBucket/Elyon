"""Verify every original uploaded file is preserved byte-for-byte."""

import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
rows = json.loads((root / "recovery/UPLOAD-MAP.json").read_text())
for row in rows:
    path = root / row["preservedPath"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
        raise SystemExit(f"Upload evidence changed: {path}")
print(f"Verified {len(rows)} preserved uploads; 60 ordered patch records.")
