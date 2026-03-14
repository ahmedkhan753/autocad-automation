import subprocess
import sys
import shutil
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

def main():
    print("=" * 50)
    print("  Building AutoCAD Room Extractor EXE (OneFile)")
    print("=" * 50)
    print()

    # Clean previous build artifacts
    for d in ["build", "dist", "AutoCAD_Room_Extractor.spec"]:
        p = BASE_DIR / d
        if p.exists():
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()

    # PyInstaller command for a Single-File EXE
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "AutoCAD_Room_Extractor",
        "--noconfirm",
        "--clean",
        "--hidden-import", "ezdxf",
        "--hidden-import", "shapely",
        "--hidden-import", "openpyxl",
        "--collect-all", "ezdxf",
        str(BASE_DIR / "main.py"),
    ]

    print(f"  Running PyInstaller...")
    result = subprocess.run(cmd, cwd=str(BASE_DIR))

    if result.returncode != 0:
        print("\n  [FAIL] Build failed! Check output above.")
        sys.exit(1)

    # Move the EXE to the project root
    exe_path = BASE_DIR / "dist" / "AutoCAD_Room_Extractor.exe"
    target_path = BASE_DIR / "AutoCAD_Room_Extractor.exe"
    if exe_path.exists():
        shutil.copy2(str(exe_path), str(target_path))
        print(f"\n  [OK] EXE moved to root: {target_path}")

    # Ensure folders exist in root
    for folder in ["input", "output", "logs"]:
        (BASE_DIR / folder).mkdir(exist_ok=True)

    # Clean up the dist/build folders entirely for simplicity
    for d in ["build", "dist", "AutoCAD_Room_Extractor.spec"]:
        p = BASE_DIR / d
        if p.exists():
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()

    print()
    print("=" * 50)
    print("  BUILD SUCCESSFUL!")
    print(f"  Single EXE location: {target_path}")
    print()
    print("  To distribute to client, just send them the")
    print("  'AutoCAD_Room_Extractor.exe' file. It will auto-create")
    print("  the config.json and folders when run!")
    print("=" * 50)

if __name__ == "__main__":
    main()
