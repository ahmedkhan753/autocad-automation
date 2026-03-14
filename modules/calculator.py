"""
Area Calculation Module
Converts raw polygon areas and perimeters to square meters and meters
based on the drawing unit configuration.
"""

import logging
from dataclasses import dataclass
from typing import List

logger = logging.getLogger("autocad_extractor.calculator")

# Conversion factors: drawing_unit → how many drawing units per meter
UNIT_CONVERSIONS = {
    "mm": {
        "area_divisor": 1_000_000,   # mm² → m²
        "length_divisor": 1_000,     # mm → m
    },
    "cm": {
        "area_divisor": 10_000,      # cm² → m²
        "length_divisor": 100,       # cm → m
    },
    "m": {
        "area_divisor": 1,           # m² → m²
        "length_divisor": 1,         # m → m
    },
}


@dataclass
class RoomData:
    """Final computed room data ready for export."""
    room_name: str
    area_sqm: float
    perimeter_m: float
    polygon_vertices: list     # List of (x, y) tuples in original units
    layer: str
    notes: str = ""


def calculate_areas(
    matched_rooms: list,
    drawing_unit: str = "mm",
) -> List[RoomData]:
    """
    Convert raw polygon areas and perimeters to metric units.

    Args:
        matched_rooms: List of MatchedRoom objects from the matcher
        drawing_unit: Unit of the drawing ("mm", "cm", or "m")

    Returns:
        List of RoomData objects with areas in sqm and perimeters in meters

    Raises:
        ValueError: If drawing_unit is not recognized
    """
    unit = drawing_unit.lower().strip()
    if unit not in UNIT_CONVERSIONS:
        raise ValueError(
            f"Unsupported drawing unit: '{drawing_unit}'. "
            f"Supported units: {', '.join(UNIT_CONVERSIONS.keys())}"
        )

    conversion = UNIT_CONVERSIONS[unit]
    area_divisor = conversion["area_divisor"]
    length_divisor = conversion["length_divisor"]

    results = []
    total_area = 0.0

    for room in matched_rooms:
        area_sqm = round(room.area_raw / area_divisor, 2)
        perimeter_m = round(room.perimeter_raw / length_divisor, 2)
        total_area += area_sqm

        room_data = RoomData(
            room_name=room.room_name,
            area_sqm=area_sqm,
            perimeter_m=perimeter_m,
            polygon_vertices=room.polygon_vertices,
            layer=room.layer,
            notes=room.notes,
        )
        results.append(room_data)

        logger.debug(
            f"Room '{room.room_name}': {area_sqm} sqm, {perimeter_m} m perimeter"
        )

    logger.info(
        f"Calculated areas for {len(results)} rooms. "
        f"Total area: {round(total_area, 2)} sqm (unit: {unit})"
    )

    return results
