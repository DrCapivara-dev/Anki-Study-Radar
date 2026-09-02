from __future__ import annotations

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
DIST = ROOT / "dist"
VERSION = "0.1.1"
OUTPUT = DIST / f"Anki_Study_Radar_v{VERSION}.ankiaddon"

FILES = [
    "__init__.py",
    "config.json",
    "config.md",
    "manifest.json",
    "README.txt",
]


def main() -> None:
    DIST.mkdir(exist_ok=True)
    missing = [name for name in FILES if not (SRC / name).is_file()]
    if missing:
        raise SystemExit(f"Missing source files: {', '.join(missing)}")

    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in FILES:
            archive.write(SRC / name, arcname=name)

    print(f"Built: {OUTPUT}")


if __name__ == "__main__":
    main()
