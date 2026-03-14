"""
Flask Web Application
Provides a clean web interface for uploading DWG/DXF files and downloading results.
"""

import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_file,
    session,
    flash,
)

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from modules.ingestion import ingest_file, cleanup_temp
from modules.parser import parse_dxf
from modules.matcher import match_tags_to_boundaries
from modules.calculator import calculate_areas
from modules.exporter import export_results

# ── App Setup ───────────────────────────────────────────────────────────

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "autocad-extractor-secret-key-change-me")
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max upload

# Directories
UPLOAD_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"
LOG_DIR = BASE_DIR / "logs"

for d in [UPLOAD_DIR, OUTPUT_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_DIR / "app.log"), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("autocad_extractor.web")


# ── Routes ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Upload page."""
    return render_template("index.html")


@app.route("/process", methods=["POST"])
def process():
    """Handle file upload and run the extraction pipeline."""
    try:
        # Validate file upload
        if "file" not in request.files:
            return render_template(
                "error.html",
                error_title="No File Uploaded",
                error_message="Please select a .dwg or .dxf file to upload.",
                hints=[
                    "Click the upload area or drag and drop a file",
                    "Accepted formats: .dwg, .dxf",
                ],
            )

        file = request.files["file"]
        if not file.filename:
            return render_template(
                "error.html",
                error_title="No File Selected",
                error_message="Please select a file before clicking Process.",
                hints=["Click the upload area to browse for a file"],
            )

        # Validate extension
        filename = file.filename
        ext = Path(filename).suffix.lower()
        if ext not in (".dwg", ".dxf"):
            return render_template(
                "error.html",
                error_title="Unsupported File Type",
                error_message=f"The file '{filename}' has an unsupported extension '{ext}'.",
                hints=[
                    "Only .dwg and .dxf files are accepted",
                    "Export your drawing as .dxf from AutoCAD if needed",
                ],
            )

        # Get form parameters
        drawing_unit = request.form.get("unit", "mm")
        layers_input = request.form.get("layers", "").strip()
        target_layers = [l.strip() for l in layers_input.split(",") if l.strip()] if layers_input else None

        # Save uploaded file
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        upload_path = UPLOAD_DIR / unique_name
        file.save(str(upload_path))
        logger.info(f"File uploaded: {filename} → {upload_path}")

        # ── Run Pipeline ────────────────────────────────────────────────

        # Step 1: Ingest
        dxf_path = ingest_file(str(upload_path))

        # Step 2: Parse
        parse_result = parse_dxf(dxf_path, target_layers=target_layers)

        if not parse_result.boundaries:
            return render_template(
                "error.html",
                error_title="No Room Boundaries Found",
                error_message=f"The drawing '{filename}' does not contain any closed polylines.",
                hints=[
                    "Ensure your drawing uses closed LWPOLYLINE or POLYLINE entities for room boundaries",
                    "Try specifying different layer names",
                    "Check if rooms are drawn as blocks (not yet supported)",
                    f"Scanned {parse_result.total_polyline_entities} polyline entities across all layers",
                ],
            )

        # Step 3: Match
        matched_rooms = match_tags_to_boundaries(parse_result.tags, parse_result.boundaries)

        # Step 4: Calculate
        room_data = calculate_areas(matched_rooms, drawing_unit=drawing_unit)

        # Step 5: Export
        files = export_results(room_data, output_dir=str(OUTPUT_DIR))

        # Store results in session
        total_area = round(sum(r.area_sqm for r in room_data), 2)
        total_perimeter = round(sum(r.perimeter_m for r in room_data), 2)

        session["results"] = {
            "filename": filename,
            "drawing_unit": drawing_unit,
            "total_rooms": len(room_data),
            "total_area": total_area,
            "total_perimeter": total_perimeter,
            "rooms": [
                {
                    "index": idx + 1,
                    "name": r.room_name,
                    "area_sqm": r.area_sqm,
                    "perimeter_m": r.perimeter_m,
                    "layer": r.layer,
                    "notes": r.notes,
                }
                for idx, r in enumerate(room_data)
            ],
            "excel_path": files["excel"],
            "csv_path": files["csv"],
            "excel_filename": files["excel_filename"],
            "csv_filename": files["csv_filename"],
            "tags_found": len(parse_result.tags),
            "polylines_found": len(parse_result.boundaries),
            "text_scanned": parse_result.total_text_entities,
            "polylines_scanned": parse_result.total_polyline_entities,
        }

        logger.info(
            f"Pipeline complete for '{filename}': "
            f"{len(room_data)} rooms, {total_area} sqm total"
        )

        return redirect(url_for("results"))

    except RuntimeError as e:
        logger.error(f"Pipeline error: {e}")
        return render_template(
            "error.html",
            error_title="Processing Error",
            error_message=str(e),
            hints=[
                "If this is a DWG file, ensure ODA File Converter or LibreDWG is installed",
                "Try exporting the drawing as .dxf from AutoCAD",
                "Check the logs for detailed error information",
            ],
        )
    except Exception as e:
        logger.exception(f"Unexpected error processing file")
        return render_template(
            "error.html",
            error_title="Unexpected Error",
            error_message=f"An unexpected error occurred: {str(e)}",
            hints=[
                "Check the application logs for details",
                "Try with a different drawing file",
                "Ensure the file is not corrupted",
            ],
        )


@app.route("/results")
def results():
    """Display extraction results."""
    result_data = session.get("results")
    if not result_data:
        return redirect(url_for("index"))
    return render_template("results.html", data=result_data)


@app.route("/download/<filetype>")
def download(filetype):
    """Download Excel or CSV file."""
    result_data = session.get("results")
    if not result_data:
        return redirect(url_for("index"))

    if filetype == "excel":
        filepath = result_data.get("excel_path")
        filename = result_data.get("excel_filename")
    elif filetype == "csv":
        filepath = result_data.get("csv_path")
        filename = result_data.get("csv_filename")
    else:
        return redirect(url_for("results"))

    if filepath and os.path.exists(filepath):
        return send_file(
            filepath,
            as_attachment=True,
            download_name=filename,
        )

    return redirect(url_for("results"))


# ── Main ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║   AutoCAD Room Area Extractor — Web UI       ║")
    print("║   http://localhost:5000                       ║")
    print("╚══════════════════════════════════════════════╝")
    print()
    app.run(debug=True, host="0.0.0.0", port=5000)
