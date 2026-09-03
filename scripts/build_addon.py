from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
OUT = ROOT / "releases" / "Anki_Study_Radar_v1.3.1_Production.ankiaddon"
PRIVATE_STATE = {"license_state.json", "device.json", "checkout_state.json", "account_state.json"}

with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as z:
    for path in sorted(SRC.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        if path.name in PRIVATE_STATE:
            continue
        z.write(path, path.relative_to(SRC).as_posix())
print(OUT)
