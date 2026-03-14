"""
Layer Parsing Module
Extracts room tags (TEXT/MTEXT) and room boundaries (closed polylines) from DXF files.
"""

import logging
import json
from pathlib import Path
from dataclasses import dataclass, field

import ezdxf

logger = logging.getLogger("autocad_extractor.parser")

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config.json"


@dataclass
class RoomTag:
    """Represents a room text label extracted from the drawing."""
    name: str
    x: float
    y: float
    layer: str


@dataclass
class RoomBoundary:
    """Represents a closed polyline boundary extracted from the drawing."""
    vertices: list  # List of (x, y) tuples
    layer: str


@dataclass
class ParseResult:
    """Combined result of parsing a DXF file."""
    tags: list = field(default_factory=list)          # List of RoomTag
    boundaries: list = field(default_factory=list)     # List of RoomBoundary
    total_text_entities: int = 0
    total_polyline_entities: int = 0


def _load_config():
    """Load configuration from config.json."""
    try:
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "room_keywords": [
                "room", "bedroom", "living", "kitchen", "bath", "toilet",
                "lounge", "dining", "store", "corridor", "garage", "study", "hall"
            ],
            "target_layers": [],
        }


def parse_dxf(
    dxf_path: str,
    target_layers: list = None,
    room_keywords: list = None,
) -> ParseResult:
    """
    Parse a DXF file to extract room tags and room boundaries.

    Args:
        dxf_path: Path to the .dxf file
        target_layers: List of layer names to filter (None = all layers)
        room_keywords: List of keywords to filter room tags (None = use config)

    Returns:
        ParseResult with extracted tags and boundaries

    Raises:
        FileNotFoundError: If DXF file doesn't exist
        RuntimeError: If DXF file is corrupted or unreadable
    """
    dxf_path = Path(dxf_path)
    if not dxf_path.exists():
        raise FileNotFoundError(f"DXF file not found: {dxf_path}")

    config = _load_config()

    # Use provided values or fall back to config
    if target_layers is None:
        target_layers = config.get("target_layers", [])
    if room_keywords is None:
        room_keywords = config.get("room_keywords", [])

    # Normalize keywords to lowercase
    room_keywords = [kw.lower() for kw in room_keywords]

    try:
        doc = ezdxf.readfile(str(dxf_path))
    except ezdxf.DXFError as e:
        raise RuntimeError(f"Failed to read DXF file: {e}")
    except Exception as e:
        raise RuntimeError(f"Unexpected error reading DXF file: {e}")

    msp = doc.modelspace()
    result = ParseResult()

    # Extract room tags
    result.tags, result.total_text_entities = _extract_room_tags(
        msp, target_layers, room_keywords
    )

    # Extract room boundaries
    result.boundaries, result.total_polyline_entities = _extract_room_boundaries(
        msp, target_layers
    )

    logger.info(
        f"Parsed DXF: {len(result.tags)} room tags, "
        f"{len(result.boundaries)} closed polylines "
        f"(from {result.total_text_entities} text entities, "
        f"{result.total_polyline_entities} polyline entities)"
    )

    return result


def _should_include_layer(entity_layer: str, target_layers: list) -> bool:
    """Check if an entity's layer should be included based on filter."""
    if not target_layers:
        return True  # No filter = include all layers
    return entity_layer.upper() in [l.upper() for l in target_layers]


def _extract_room_tags(msp, target_layers: list, room_keywords: list):
    """
    Extract room name tags from TEXT and MTEXT entities.

    Returns:
        Tuple of (list of RoomTag, total text entities scanned)
    """
    tags = []
    total_scanned = 0

    # Process TEXT entities
    for entity in msp.query("TEXT"):
        total_scanned += 1

        if not _should_include_layer(entity.dxf.layer, target_layers):
            continue

        text = entity.dxf.text.strip()
        if not text:
            continue

        # Check if text matches any room keyword
        if _matches_room_keyword(text, room_keywords):
            insert = entity.dxf.insert
            tag = RoomTag(
                name=text,
                x=insert.x,
                y=insert.y,
                layer=entity.dxf.layer,
            )
            tags.append(tag)
            logger.debug(f"Found room tag: '{text}' at ({insert.x:.1f}, {insert.y:.1f})")

    # Process MTEXT entities
    for entity in msp.query("MTEXT"):
        total_scanned += 1

        if not _should_include_layer(entity.dxf.layer, target_layers):
            continue

        # MTEXT can contain formatting codes; get plain text
        text = entity.plain_text().strip()
        if not text:
            continue

        if _matches_room_keyword(text, room_keywords):
            insert = entity.dxf.insert
            tag = RoomTag(
                name=text,
                x=insert.x,
                y=insert.y,
                layer=entity.dxf.layer,
            )
            tags.append(tag)
            logger.debug(f"Found room tag (MTEXT): '{text}' at ({insert.x:.1f}, {insert.y:.1f})")

    logger.info(f"Extracted {len(tags)} room tags from {total_scanned} text entities")
    return tags, total_scanned


def _matches_room_keyword(text: str, keywords: list) -> bool:
    """
    Check if text matches any room keyword (case-insensitive, partial match).

    Args:
        text: The text to check
        keywords: List of lowercase keywords

    Returns:
        True if any keyword is found in the text
    """
    if not keywords:
        return True  # No keywords = include all text
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def _extract_room_boundaries(msp, target_layers: list):
    """
    Extract closed polyline boundaries.

    Returns:
        Tuple of (list of RoomBoundary, total polyline entities scanned)
    """
    boundaries = []
    total_scanned = 0

    # Process LWPOLYLINE entities
    for entity in msp.query("LWPOLYLINE"):
        total_scanned += 1

        if not _should_include_layer(entity.dxf.layer, target_layers):
            continue

        if not entity.closed:
            continue

        # Extract vertices (LWPOLYLINE stores 2D points)
        vertices = [(point[0], point[1]) for point in entity.get_points(format="xy")]

        if len(vertices) < 3:
            logger.debug(f"Skipping polyline with fewer than 3 vertices on layer {entity.dxf.layer}")
            continue

        boundary = RoomBoundary(
            vertices=vertices,
            layer=entity.dxf.layer,
        )
        boundaries.append(boundary)

    # Process POLYLINE entities (older 2D polylines)
    for entity in msp.query("POLYLINE"):
        total_scanned += 1

        if not _should_include_layer(entity.dxf.layer, target_layers):
            continue

        if not entity.is_closed:
            continue

        # Extract vertices from POLYLINE
        vertices = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]

        if len(vertices) < 3:
            logger.debug(f"Skipping polyline with fewer than 3 vertices on layer {entity.dxf.layer}")
            continue

        boundary = RoomBoundary(
            vertices=vertices,
            layer=entity.dxf.layer,
        )
        boundaries.append(boundary)

    logger.info(
        f"Extracted {len(boundaries)} closed polylines from {total_scanned} polyline entities"
    )
    return boundaries, total_scanned
