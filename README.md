# AutoCAD Room Area Extractor

A Python-based CLI + Web UI tool that extracts room areas from AutoCAD DWG/DXF drawings and exports structured Excel and CSV reports.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Features

- **DWG & DXF Support** — Automatic DWG-to-DXF conversion via ODA File Converter or LibreDWG
- **Smart Room Detection** — Extracts room labels (TEXT/MTEXT) and boundaries (closed polylines)
- **Spatial Matching** — Matches labels to rooms using point-in-polygon analysis
- **Area Calculation** — Supports mm/cm/m drawing units with automatic sqm conversion
- **Excel Export** — Formatted spreadsheet with headers, totals, and raw vertex data
- **CSV Export** — Clean data export for further processing
- **Web Interface** — Drag-and-drop upload UI for non-technical users
- **CLI Interface** — Full pipeline via command line for automation

## Quick Start

### Prerequisites

- Python 3.10+
- (Optional) [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) for DWG support

### Installation

```bash
# Clone the repository
git clone https://github.com/ahmedkhan753/autocad-automation.git
cd autocad-automation

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Generate Test Data

```bash
python tests/generate_test_dxf.py
```

This creates `tests/sample_drawing.dxf` with 5 mock rooms.

## Usage

### CLI

```bash
# Basic usage (DXF file, mm units)
python main.py --input tests/sample_drawing.dxf --unit mm

# Specify layers and output directory
python main.py --input drawing.dxf --unit mm --layers "A-ROOM,ROOMS" --output ./results

# Process a DWG file (requires ODA converter)
python main.py --input plan.dwg --unit cm
```

### Web UI

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

1. Drag and drop a `.dwg` or `.dxf` file
2. Select drawing unit (mm / cm / m)
3. Optionally specify target layer names
4. Click **Process File**
5. Download results as Excel or CSV

### One-Click Launcher (Linux/Mac)

```bash
chmod +x run.sh
./run.sh
```

## Configuration

Edit `config.json` to customize:

```json
{
  "drawing_unit": "mm",
  "target_layers": [],
  "room_keywords": ["room", "bedroom", "living", "kitchen", "bath", "toilet",
                     "lounge", "dining", "store", "corridor", "garage", "study", "hall"],
  "oda_converter_path": "",
  "output_dir": "output/"
}
```

| Setting | Description |
|---------|-------------|
| `drawing_unit` | Default unit: `mm`, `cm`, or `m` |
| `target_layers` | Layer names to scan (empty = all layers) |
| `room_keywords` | Keywords for filtering room text labels |
| `oda_converter_path` | Path to ODA File Converter executable |
| `output_dir` | Output directory for Excel/CSV files |

## DWG Support (ODA File Converter)

To process `.dwg` files, install the free ODA File Converter:

1. Download from [opendesign.com](https://www.opendesign.com/guestfiles/oda_file_converter)
2. Install and note the installation path
3. Set `oda_converter_path` in `config.json`:
   ```json
   {
     "oda_converter_path": "C:/Program Files/ODA/ODAFileConverter/ODAFileConverter.exe"
   }
   ```

Alternatively, install [LibreDWG](https://www.gnu.org/software/libredwg/) and ensure `dwg2dxf` is on your PATH.

## Project Structure

```
autocad-extractor/
├── app.py                  # Flask web app
├── main.py                 # CLI entry point
├── config.json             # Configuration
├── requirements.txt        # Dependencies
├── run.sh                  # Bootstrap launcher
├── modules/
│   ├── ingestion.py        # File ingestion & DWG conversion
│   ├── parser.py           # DXF layer parsing
│   ├── matcher.py          # Spatial tag-to-boundary matching
│   ├── calculator.py       # Area & perimeter calculation
│   └── exporter.py         # Excel & CSV export
├── templates/              # Flask HTML templates
├── static/                 # CSS stylesheet
├── tests/                  # Test data & scripts
├── temp/                   # Converted DXF files (auto-cleaned)
├── output/                 # Generated Excel/CSV files
└── logs/                   # Application logs
```

## Pipeline

```
Input (.dwg/.dxf)
  → Ingestion (convert DWG if needed)
  → Parsing (extract TEXT + closed POLYLINE entities)
  → Matching (point-in-polygon spatial matching)
  → Calculation (area in sqm, perimeter in m)
  → Export (Excel + CSV with formatting)
```

## License

MIT License
