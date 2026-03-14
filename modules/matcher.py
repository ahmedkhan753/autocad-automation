"""
Spatial Matching Module
Matches room tags (text labels) to room boundaries (closed polylines)
using Shapely point-in-polygon tests.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from shapely.geometry import Point, Polygon
from shapely.validation import make_valid

logger = logging.getLogger("autocad_extractor.matcher")


@dataclass
class MatchedRoom:
    """A room with its matched name, geometry, and computed properties."""
    room_name: str
    polygon_vertices: list     # List of (x, y) tuples
    area_raw: float            # Area in drawing units squared
    perimeter_raw: float       # Perimeter in drawing units
    layer: str
    notes: str = ""


def match_tags_to_boundaries(tags, boundaries) -> List[MatchedRoom]:
    """
    Match room tags to room boundaries using spatial point-in-polygon tests.

    For each tag, find which polygon contains the tag's insertion point.

    Edge cases handled:
    - Tag outside all polygons → assigned to nearest polygon by centroid distance
    - Multiple tags inside one polygon → names concatenated with " / "
    - Polygon with no tag → labelled "Unlabelled Room [N]"

    Args:
        tags: List of RoomTag (from parser)
        boundaries: List of RoomBoundary (from parser)

    Returns:
        List of MatchedRoom objects with names, vertices, raw area/perimeter
    """
    if not boundaries:
        logger.warning("No room boundaries found — nothing to match")
        return []

    # Build Shapely polygons from boundaries
    polygon_data = []
    for i, boundary in enumerate(boundaries):
        try:
            poly = Polygon(boundary.vertices)
            if not poly.is_valid:
                poly = make_valid(poly)
                # make_valid might return a GeometryCollection; take largest polygon
                if poly.geom_type == "MultiPolygon":
                    poly = max(poly.geoms, key=lambda g: g.area)
                elif poly.geom_type != "Polygon":
                    logger.warning(
                        f"Boundary {i} on layer '{boundary.layer}' could not be fixed to a valid polygon, skipping"
                    )
                    continue

            polygon_data.append({
                "index": i,
                "polygon": poly,
                "boundary": boundary,
                "tags": [],  # Tags that fall inside this polygon
            })
        except Exception as e:
            logger.warning(f"Failed to create polygon for boundary {i}: {e}")
            continue

    if not polygon_data:
        logger.warning("No valid polygons could be created from boundaries")
        return []

    # Match each tag to a polygon
    unmatched_tags = []

    for tag in tags:
        point = Point(tag.x, tag.y)
        matched = False

        for pd in polygon_data:
            if pd["polygon"].contains(point):
                pd["tags"].append(tag)
                matched = True
                logger.debug(
                    f"Tag '{tag.name}' matched to polygon {pd['index']} "
                    f"on layer '{pd['boundary'].layer}'"
                )
                break

        if not matched:
            unmatched_tags.append(tag)

    # Handle unmatched tags — assign to nearest polygon by centroid distance
    for tag in unmatched_tags:
        point = Point(tag.x, tag.y)
        nearest_pd = min(
            polygon_data,
            key=lambda pd: pd["polygon"].centroid.distance(point),
        )
        nearest_pd["tags"].append(tag)
        logger.info(
            f"Tag '{tag.name}' was outside all polygons — assigned to nearest "
            f"polygon {nearest_pd['index']} on layer '{nearest_pd['boundary'].layer}'"
        )

    # Build matched rooms
    matched_rooms = []
    unlabelled_count = 0

    for pd in polygon_data:
        poly = pd["polygon"]
        boundary = pd["boundary"]
        tag_list = pd["tags"]

        # Determine room name
        if tag_list:
            room_name = " / ".join(t.name for t in tag_list)
            notes = ""
            if len(tag_list) > 1:
                notes = f"Multiple tags found ({len(tag_list)})"
        else:
            unlabelled_count += 1
            room_name = f"Unlabelled Room {unlabelled_count}"
            notes = "No matching text tag found inside this boundary"

        matched_room = MatchedRoom(
            room_name=room_name,
            polygon_vertices=boundary.vertices,
            area_raw=poly.area,
            perimeter_raw=poly.length,
            layer=boundary.layer,
            notes=notes,
        )
        matched_rooms.append(matched_room)

    logger.info(
        f"Matching complete: {len(matched_rooms)} rooms, "
        f"{unlabelled_count} unlabelled, "
        f"{len(unmatched_tags)} tags reassigned by proximity"
    )

    return matched_rooms
