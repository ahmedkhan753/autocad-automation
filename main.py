"""
CLI Entry Point
Runs the full AutoCAD room extraction pipeline from the command line.
"""

import argparse
import io
import json
import logging
import os
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from modules.ingestion import ingest_file, cleanup_temp
from modules.parser import parse_dxf
from modules.matcher import match_tags_to_boundaries
from modules.calculator import calculate_areas
from modules.exporter import export_results


def setup_logging():
    """Configure logging to both console and file."""
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.FileHandler(str(log_dir / "app.log"), encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def print_status(message: str, success: bool = True):
    """Print a status message."""
    symbol = "[OK]" if success else "[FAIL]"
    print(f"  {symbol} {message}")


def main():
    parser = argparse.ArgumentParser(
        description="AutoCAD Room Area Extractor — Extract room areas from DWG/DXF files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --input drawing.dxf --unit mm
  python main.py --input plan.dwg --unit mm --layers "A-ROOM,ROOMS" --output ./results
  python main.py --input drawing.dxf --unit cm --layers "0"
        """,
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input .dwg or .dxf file",
    )
    parser.add_argument(
        "--unit", "-u",
        default="mm",
        choices=["mm", "cm", "m"],
        help="Drawing unit (default: mm)",
    )
    parser.add_argument(
        "--layers", "-l",
        default="",
        help='Comma-separated list of layer names to scan (default: all layers)',
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="Output directory (default: output/)",
    )

    args = parser.parse_args()

    setup_logging()
    logger = logging.getLogger("autocad_extractor.cli")

    print()
    print("=" * 48)
    print("   AutoCAD Room Area Extractor")
    print("=" * 48)
    print()

    # Parse layer filter
    target_layers = []
    if args.layers:
        target_layers = [l.strip() for l in args.layers.split(",") if l.strip()]

    # Determine output directory
    output_dir = args.output if args.output else str(BASE_DIR / "output")

    try:
        # Step 1: Ingest file
        print("  [1/5] Ingesting file...")
        dxf_path = ingest_file(args.input)
        ext = Path(args.input).suffix.lower()
        if ext == ".dwg":
            print_status("DWG file converted to DXF")
        else:
            print_status("DXF file loaded")

        # Step 2: Parse DXF
        print("  [2/5] Parsing drawing layers...")
        parse_result = parse_dxf(
            dxf_path,
            target_layers=target_layers if target_layers else None,
        )
        print_status(
            f"{parse_result.total_polyline_entities} polyline entities scanned, "
            f"{len(parse_result.boundaries)} closed polylines found"
        )
        print_status(
            f"{parse_result.total_text_entities} text entities scanned, "
            f"{len(parse_result.tags)} room tags found"
        )

        if not parse_result.boundaries:
            print_status("No closed polylines found -- cannot extract rooms", success=False)
            print()
            print("  Troubleshooting:")
            print("    - Ensure your drawing contains closed polylines (LWPOLYLINE/POLYLINE)")
            print("    - Try specifying different layer names with --layers")
            print("    - Check if the drawing uses blocks instead of polylines")
            sys.exit(1)

        # Step 3: Match tags to boundaries
        print("  [3/5] Matching room tags to boundaries...")
        matched_rooms = match_tags_to_boundaries(
            parse_result.tags, parse_result.boundaries
        )
        print_status(f"{len(matched_rooms)} rooms matched")

        # Step 4: Calculate areas
        print("  [4/5] Calculating areas...")
        room_data = calculate_areas(matched_rooms, drawing_unit=args.unit)
        total_area = sum(r.area_sqm for r in room_data)
        print_status(f"Total area: {round(total_area, 2)} sqm (unit: {args.unit})")

        # Step 5: Export results
        print("  [5/5] Exporting results...")
        files = export_results(room_data, output_dir=output_dir)
        print_status(f"Excel saved: {files['excel']}")
        print_status(f"CSV saved:   {files['csv']}")

        # Summary
        print()
        print("  -- Room Schedule " + "-" * 30)
        print(f"  {'#':<4} {'Room Name':<30} {'Area (sqm)':<12} {'Perimeter (m)':<14}")
        print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*14}")
        for idx, room in enumerate(room_data, 1):
            print(
                f"  {idx:<4} {room.room_name:<30} {room.area_sqm:<12.2f} {room.perimeter_m:<14.2f}"
            )
        print(f"  {'-'*4} {'-'*30} {'-'*12} {'-'*14}")
        print(f"  {'':4} {'TOTAL':<30} {total_area:<12.2f}")
        print()

        # Cleanup
        cleanup_temp()
        print_status("Temp files cleaned up")
        print()

        sys.exit(0)

    except FileNotFoundError as e:
        print_status(str(e), success=False)
        logger.error(str(e))
        sys.exit(1)
    except ValueError as e:
        print_status(str(e), success=False)
        logger.error(str(e))
        sys.exit(1)
    except RuntimeError as e:
        print_status(str(e), success=False)
        logger.error(str(e))
        sys.exit(1)
    except Exception as e:
        print_status(f"Unexpected error: {e}", success=False)
        logger.exception("Unexpected error in CLI pipeline")
        sys.exit(1)


if __name__ == "__main__":
    main()
