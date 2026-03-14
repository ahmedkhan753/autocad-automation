"""
AutoCAD Room Area Extractor
===========================
Simple script: drop .dwg/.dxf files into the 'input' folder, run this script,
and find Excel + CSV results in the 'output' folder.
"""

import io
import json
import logging
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding (use try/except in case sys.stdout is not ready)
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# Determine base directory (works for both script and frozen EXE)
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent
    # Add project root to path only for local execution
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))

from modules.ingestion import ingest_file, cleanup_temp
from modules.parser import parse_dxf
from modules.matcher import match_tags_to_boundaries
from modules.calculator import calculate_areas
from modules.exporter import export_results

# ── Directories ─────────────────────────────────────────────────────────
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "config.json"


def setup_logging():
    """Configure logging to file."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(str(LOG_DIR / "app.log"), encoding="utf-8"),
        ],
    )


def load_config():
    """Load configuration from config.json. Create if missing."""
    defaults = {
        "drawing_unit": "mm",
        "target_layers": [],
        "room_keywords": [
            "room", "bedroom", "living", "kitchen", "bath", "toilet",
            "lounge", "dining", "store", "corridor", "garage", "study", "hall"
        ],
        "oda_converter_path": "C:/Program Files/ODA/ODAFileConverter 27.1.0/ODAFileConverter.exe",
        "output_dir": "output/",
    }
    try:
        if not CONFIG_PATH.exists():
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(defaults, f, indent=2)
            return defaults

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
            # Merge with defaults
            for key, val in defaults.items():
                config.setdefault(key, val)
            return config
    except Exception as e:
        print(f"  [WARN] Failed to read/write config.json: {e}")
        return defaults


def print_banner():
    print()
    print("=" * 52)
    print("   AutoCAD Room Area Extractor")
    print("   Drop .dwg / .dxf files into the 'input' folder")
    print("=" * 52)
    print()


def process_file(filepath: Path, config: dict) -> bool:
    """
    Process a single .dwg/.dxf file through the full pipeline.
    Returns True on success, False on failure.
    """
    filename = filepath.name
    drawing_unit = config.get("drawing_unit", "mm")
    target_layers = config.get("target_layers", []) or None

    print(f"  Processing: {filename}")
    print(f"  Unit: {drawing_unit} | Layers: {target_layers or 'ALL'}")
    print()

    try:
        # Step 1: Ingest
        print("  [1/5] Ingesting file...")
        dxf_path = ingest_file(
            str(filepath),
            oda_converter_path=config.get("oda_converter_path", ""),
            base_dir=BASE_DIR
        )
        ext = filepath.suffix.lower()
        if ext == ".dwg":
            print("  [OK]  DWG converted to DXF")
        else:
            print("  [OK]  DXF file loaded")

        # Step 2: Parse
        print("  [2/5] Parsing drawing layers...")
        parse_result = parse_dxf(dxf_path, target_layers=target_layers)
        print(f"  [OK]  {len(parse_result.boundaries)} closed polylines found")
        print(f"  [OK]  {len(parse_result.tags)} room tags found")

        if not parse_result.boundaries:
            print("  [FAIL] No closed polylines found -- cannot extract rooms")
            print()
            print("  Troubleshooting:")
            print("    - Ensure your drawing has closed polylines (LWPOLYLINE/POLYLINE)")
            print("    - Try different layer names in config.json")
            print("    - Check if rooms are drawn as blocks (not supported)")
            return False

        # Step 3: Match
        print("  [3/5] Matching room tags to boundaries...")
        matched_rooms = match_tags_to_boundaries(parse_result.tags, parse_result.boundaries)
        print(f"  [OK]  {len(matched_rooms)} rooms matched")

        # Step 4: Calculate
        print("  [4/5] Calculating areas...")
        room_data = calculate_areas(matched_rooms, drawing_unit=drawing_unit)
        total_area = sum(r.area_sqm for r in room_data)
        print(f"  [OK]  Total area: {round(total_area, 2)} sqm")

        # Step 5: Export
        print("  [5/5] Exporting results...")
        files = export_results(room_data, output_dir=str(OUTPUT_DIR))
        print(f"  [OK]  Excel: {files['excel_filename']}")
        print(f"  [OK]  CSV:   {files['csv_filename']}")

        # Print summary table
        print()
        print("  -- Room Schedule " + "-" * 32)
        print(f"  {'#':<4} {'Room Name':<30} {'Area (sqm)':<12} {'Perimeter (m)':<14}")
        print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*14}")
        for idx, room in enumerate(room_data, 1):
            print(f"  {idx:<4} {room.room_name:<30} {room.area_sqm:<12.2f} {room.perimeter_m:<14.2f}")
        print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*14}")
        print(f"  {'':4} {'TOTAL':<30} {total_area:<12.2f}")
        print()

        return True

    except Exception as e:
        logging.getLogger("autocad_extractor").exception(f"Error processing {filename}")
        print(f"  [FAIL] Error: {e}")
        print()
        return False


def main():
    setup_logging()
    print_banner()

    # Create directories if they don't exist
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load config
    config = load_config()

    # Find all .dwg and .dxf files in input folder
    input_files = []
    for ext in ("*.dwg", "*.dxf"):
        input_files.extend(INPUT_DIR.glob(ext))

    if not input_files:
        print("  No .dwg or .dxf files found in the 'input' folder!")
        print()
        print(f"  Please place your drawing files in:")
        print(f"    {INPUT_DIR}")
        print()
        print("  Then run this program again.")
        print()
        input("  Press Enter to exit...")
        sys.exit(1)

    print(f"  Found {len(input_files)} file(s) to process:")
    for f in input_files:
        print(f"    - {f.name}")
    print()
    print("-" * 52)

    # Process each file
    success_count = 0
    fail_count = 0

    for filepath in input_files:
        print()
        result = process_file(filepath, config)
        if result:
            success_count += 1
        else:
            fail_count += 1
        print("-" * 52)

    # Cleanup temp
    cleanup_temp(base_dir=BASE_DIR)

    # Final summary
    print()
    print("=" * 52)
    print(f"  DONE! {success_count} file(s) processed successfully")
    if fail_count:
        print(f"  {fail_count} file(s) failed (check logs/app.log)")
    print(f"  Results saved to: {OUTPUT_DIR}")
    print("=" * 52)
    print()
    input("  Press Enter to exit...")

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == "__main__":
    main()
