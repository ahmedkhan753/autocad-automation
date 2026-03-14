"""
File Ingestion Module
Handles .dwg and .dxf file ingestion with automatic DWG-to-DXF conversion.
"""

import os
import shutil
import subprocess
import logging
import json
from pathlib import Path

logger = logging.getLogger("autocad_extractor.ingestion")

# Base directory for the project
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
CONFIG_PATH = BASE_DIR / "config.json"


def load_config():
    """Load configuration from config.json."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("config.json not found, using defaults")
        return {
            "drawing_unit": "mm",
            "target_layers": [],
            "room_keywords": [],
            "oda_converter_path": "",
            "output_dir": "output/",
        }
    except json.JSONDecodeError as e:
        logger.error(f"Invalid config.json: {e}")
        raise ValueError(f"Configuration file is malformed: {e}")


def ensure_temp_dir():
    """Create temp directory if it doesn't exist."""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR


def ingest_file(filepath: str) -> str:
    """
    Ingest a .dwg or .dxf file and return the path to a valid .dxf file.

    If the input is .dwg, it is converted to .dxf using ODA File Converter
    or LibreDWG's dwg2dxf. If the input is .dxf, it is copied to temp directory.

    Args:
        filepath: Path to the input .dwg or .dxf file

    Returns:
        Path to the .dxf file ready for parsing

    Raises:
        FileNotFoundError: If input file doesn't exist
        ValueError: If file has unsupported extension
        RuntimeError: If DWG conversion fails
    """
    filepath = Path(filepath).resolve()

    # Validate file exists
    if not filepath.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")

    # Validate extension
    ext = filepath.suffix.lower()
    if ext not in (".dwg", ".dxf"):
        raise ValueError(
            f"Unsupported file type '{ext}'. Only .dwg and .dxf files are accepted."
        )

    temp_dir = ensure_temp_dir()

    if ext == ".dxf":
        # Copy DXF directly to temp directory
        dest = temp_dir / filepath.name
        shutil.copy2(str(filepath), str(dest))
        logger.info(f"DXF file copied to temp: {dest}")
        return str(dest)

    # DWG file — needs conversion
    logger.info(f"DWG file detected, attempting conversion: {filepath}")
    return _convert_dwg_to_dxf(filepath, temp_dir)


def _convert_dwg_to_dxf(dwg_path: Path, temp_dir: Path) -> str:
    """
    Convert a .dwg file to .dxf using ODA File Converter or LibreDWG.

    Args:
        dwg_path: Path to the input .dwg file
        temp_dir: Directory to store the converted .dxf file

    Returns:
        Path to the converted .dxf file

    Raises:
        RuntimeError: If conversion fails
    """
    config = load_config()
    oda_path = config.get("oda_converter_path", "")

    # Try ODA File Converter first
    if oda_path and os.path.exists(oda_path):
        return _convert_with_oda(dwg_path, temp_dir, oda_path)

    # Try LibreDWG's dwg2dxf
    if shutil.which("dwg2dxf"):
        return _convert_with_libredwg(dwg_path, temp_dir)

    # Neither converter found
    raise RuntimeError(
        "No DWG-to-DXF converter found.\n\n"
        "Please install one of the following:\n"
        "  1. ODA File Converter (free): https://www.opendesign.com/guestfiles/oda_file_converter\n"
        "     Then set 'oda_converter_path' in config.json\n"
        "  2. LibreDWG (open source): https://www.gnu.org/software/libredwg/\n"
        "     Ensure 'dwg2dxf' is available on your system PATH\n\n"
        "Alternatively, export your drawing as .dxf from AutoCAD directly."
    )


def _convert_with_oda(dwg_path: Path, temp_dir: Path, oda_path: str) -> str:
    """
    Convert DWG to DXF using ODA File Converter.

    ODA File Converter CLI syntax:
      ODAFileConverter <input_dir> <output_dir> <version> <file_type> <recurse> <audit>
      version: "ACAD2018" (or other AutoCAD version)
      file_type: "DXF" for .dxf output, "0" for binary
    """
    input_dir = str(dwg_path.parent)
    output_dir = str(temp_dir)
    dwg_filename = dwg_path.name
    expected_output = temp_dir / dwg_path.with_suffix(".dxf").name

    try:
        # ODA File Converter processes entire directories
        # We copy the single file to a staging area to avoid processing extras
        staging_dir = temp_dir / "_oda_staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        staged_file = staging_dir / dwg_filename
        shutil.copy2(str(dwg_path), str(staged_file))

        cmd = [
            oda_path,
            str(staging_dir),  # Input directory
            str(temp_dir),     # Output directory
            "ACAD2018",        # Output version
            "DXF",             # Output file type
            "0",               # Non-recursive
            "1",               # Audit and fix errors
        ]

        logger.info(f"Running ODA File Converter: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Clean up staging
        shutil.rmtree(str(staging_dir), ignore_errors=True)

        if result.returncode != 0:
            logger.error(f"ODA conversion failed: {result.stderr}")
            raise RuntimeError(
                f"ODA File Converter failed (exit code {result.returncode}).\n"
                f"Error: {result.stderr.strip() or 'Unknown error'}"
            )

        if not expected_output.exists():
            raise RuntimeError(
                "ODA File Converter completed but output .dxf file was not created.\n"
                "The DWG file may be corrupted or in an unsupported format."
            )

        logger.info(f"DWG converted successfully: {expected_output}")
        return str(expected_output)

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "DWG conversion timed out after 120 seconds.\n"
            "The file may be too large or corrupted."
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"ODA File Converter not found at: {oda_path}\n"
            "Please verify the 'oda_converter_path' in config.json"
        )


def _convert_with_libredwg(dwg_path: Path, temp_dir: Path) -> str:
    """Convert DWG to DXF using LibreDWG's dwg2dxf command."""
    output_path = temp_dir / dwg_path.with_suffix(".dxf").name

    try:
        cmd = ["dwg2dxf", "-o", str(output_path), str(dwg_path)]
        logger.info(f"Running dwg2dxf: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            logger.error(f"dwg2dxf conversion failed: {result.stderr}")
            raise RuntimeError(
                f"LibreDWG conversion failed (exit code {result.returncode}).\n"
                f"Error: {result.stderr.strip() or 'Unknown error'}"
            )

        if not output_path.exists():
            raise RuntimeError(
                "dwg2dxf completed but output .dxf file was not created.\n"
                "The DWG file may be corrupted or in an unsupported format."
            )

        logger.info(f"DWG converted successfully: {output_path}")
        return str(output_path)

    except subprocess.TimeoutExpired:
        raise RuntimeError(
            "DWG conversion timed out after 120 seconds.\n"
            "The file may be too large or corrupted."
        )


def cleanup_temp():
    """Remove all files in the temp directory."""
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(str(TEMP_DIR))
            TEMP_DIR.mkdir(parents=True, exist_ok=True)
            logger.info("Temp directory cleaned")
    except OSError as e:
        logger.warning(f"Failed to clean temp directory: {e}")
