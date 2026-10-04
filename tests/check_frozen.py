"""Run: python tests/check_frozen.py
Proves the verified backend is untouched: compares SHA-256 of every frozen file with FROZEN.sha256."""
import hashlib, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
bad = 0
for line in (ROOT / "FROZEN.sha256").read_text().splitlines():
    digest, name = line.split(None, 1)
    f = ROOT / name.strip()
    ok = f.exists() and hashlib.sha256(f.read_bytes()).hexdigest() == digest
    bad += not ok
    print("PASS" if ok else "FAIL", name.strip())
print("\nRESULT:", "backend is FROZEN and unchanged" if not bad else "a frozen file was modified. Revert it.")
sys.exit(1 if bad else 0)
