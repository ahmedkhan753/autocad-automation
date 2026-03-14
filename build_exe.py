"""
Build script — Creates a standalone EXE using PyInstaller.
Run this from within the venv:
    python build_exe.py
"""

import subprocess
import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def main():
    print("=" * 50)
    print("  Building AutoCAD Room Extractor EXE")
    print("=" * 50)
    print()

    # Clean previous build
    for d in ["build", "dist"]:
        p = BASE_DIR / d
        if p.exists():
            shutil.rmtree(str(p))
            print(f"  Cleaned {d}/")

    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--name", "AutoCAD_Room_Extractor",
        "--noconfirm",
        "--clean",
        "--add-data", f"config.json{os.pathsep}.",
        "--add-data", f"modules{os.pathsep}modules",
        "--hidden-import", "ezdxf",
        "--hidden-import", "shapely",
        "--hidden-import", "openpyxl",
        "--collect-all", "ezdxf",
        str(BASE_DIR / "main.py"),
    ]

    print(f"  Running PyInstaller...")
    print()

    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode != 0:
        print()
        print("  [FAIL] Build failed! Check output above.")
        sys.exit(1)

    # Create input/output folders in dist
    dist_dir = BASE_DIR / "dist" / "AutoCAD_Room_Extractor"
    (dist_dir / "input").mkdir(exist_ok=True)
    (dist_dir / "output").mkdir(exist_ok=True)
    (dist_dir / "logs").mkdir(exist_ok=True)

    # Copy config.json to dist
    shutil.copy2(str(BASE_DIR / "config.json"), str(dist_dir / "config.json"))

    print()
    print("=" * 50)
    print("  BUILD SUCCESSFUL!")
    print(f"  EXE location: dist/AutoCAD_Room_Extractor/")
    print()
    print("  To distribute to client, zip the entire")
    print("  'AutoCAD_Room_Extractor' folder.")
    print("=" * 50)


if __name__ == "__main__":
    import os
    main()
