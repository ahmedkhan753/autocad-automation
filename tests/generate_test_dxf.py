"""
Test DXF Generator
Creates a sample DXF file with 5 mock rooms for testing the extraction pipeline.
"""

import ezdxf
from pathlib import Path


def generate_test_dxf(output_path: str = None):
    """
    Generate a sample DXF file with 5 rooms as closed polylines with text labels.

    Rooms (all coordinates in mm):
    1. Bedroom    — 4000 x 3500 mm = 14.00 sqm
    2. Kitchen    — 3500 x 3000 mm = 10.50 sqm
    3. Living Room — 5000 x 4000 mm = 20.00 sqm
    4. Bathroom   — 2500 x 2000 mm =  5.00 sqm
    5. Corridor   — 6000 x 1500 mm =  9.00 sqm
    """
    if output_path is None:
        output_path = str(Path(__file__).parent / "sample_drawing.dxf")

    doc = ezdxf.new("R2010")
    msp = doc.modelspace()

    # Create a layer for rooms
    doc.layers.add("A-ROOM", color=3)

    # Define rooms: (name, x_offset, y_offset, width, height)
    rooms = [
        ("Bedroom 1",     0,      0,     4000, 3500),
        ("Kitchen",       4500,   0,     3500, 3000),
        ("Living Room",   0,      4000,  5000, 4000),
        ("Bathroom",      5500,   4000,  2500, 2000),
        ("Corridor",      0,      8500,  6000, 1500),
    ]

    for name, x, y, w, h in rooms:
        # Create closed polyline (room boundary)
        points = [
            (x, y),
            (x + w, y),
            (x + w, y + h),
            (x, y + h),
        ]
        msp.add_lwpolyline(
            points,
            close=True,
            dxfattribs={"layer": "A-ROOM"},
        )

        # Add room label (TEXT entity) at center of room
        cx = x + w / 2
        cy = y + h / 2
        msp.add_text(
            name,
            dxfattribs={
                "layer": "A-ROOM",
                "height": 200,
                "insert": (cx, cy),
            },
        )

    doc.saveas(output_path)
    print(f"[✓] Sample DXF file created: {output_path}")
    print(f"    Contains {len(rooms)} rooms on layer 'A-ROOM'")
    print()
    print("    Expected areas (drawing unit = mm):")
    for name, x, y, w, h in rooms:
        area_sqm = (w * h) / 1_000_000
        print(f"      {name:<15} → {area_sqm:.2f} sqm")

    return output_path


if __name__ == "__main__":
    generate_test_dxf()
