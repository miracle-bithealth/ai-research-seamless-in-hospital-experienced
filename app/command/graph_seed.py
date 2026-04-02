"""Seed graph data from editor JSON files into MongoDB.

Reads base_data + spatial_data per floor from current_data_sample/
or data/graphs/, merges them into a single MongoDB document per building,
and saves via GraphRepository.

Usage:
    python -m app.command.graph_seed
"""

import asyncio
import json
import os
import sys
import logging

logger = logging.getLogger(__name__)

# Floor config: floor number -> (spatial_data file, base_data file)
SHLV_FLOORS = {
    1: ("LT1_spatial_data.json", "LT1_base_data.json"),
    2: ("LT2_spatial_data.json", "LT2_base_data.json"),
    5: ("LT5_spatial_data.json", "LT5_base_data.json"),
}

BUILDING_ID = "shlv"
BUILDING_NAME = "Siloam Hospitals Lippo Village"

# Search paths for data files (relative to project root)
DATA_DIRS = [
    "current_data_sample",
    "../current_data_sample",
    "data/graphs",
]


def find_data_file(filename: str) -> str | None:
    for directory in DATA_DIRS:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return path
    return None


def load_json(path: str) -> list | dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def merge_floor_data(
    spatial_data: list[dict],
    base_data: list[dict],
    floor: int,
) -> list[dict]:
    """Merge spatial and base data into MongoDB node format."""
    base_lookup = {item["id"]: item for item in base_data}
    merged = []

    for spatial in spatial_data:
        node_id = spatial["id"]
        base = base_lookup.get(node_id, {})

        aliases_raw = base.get("aliases", "")
        if isinstance(aliases_raw, str):
            aliases = [a.strip() for a in aliases_raw.split(",") if a.strip()]
        else:
            aliases = aliases_raw

        keywords_raw = base.get("keywords", "")
        if isinstance(keywords_raw, str):
            keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]
        else:
            keywords = keywords_raw

        node = {
            "id": node_id,
            "type": spatial.get("type", "junction"),
            "floor": floor,
            "cx": spatial.get("cx", 0),
            "cy": spatial.get("cy", 0),
            "connection": spatial.get("connection", []),
            "objectName": base.get("label", ""),
            "categoryId": base.get("room-type", ""),
            "label": base.get("description", ""),
            "aliases": aliases,
            "keywords": keywords,
            "slug": base.get("slug", ""),
            "wings": base.get("wings", ""),
            "accessible": True,
        }
        merged.append(node)

    return merged


async def seed():
    from app.repositories.GraphRepository import graphRepository

    all_nodes = []
    floors_found = []

    for floor_num, (spatial_file, base_file) in SHLV_FLOORS.items():
        spatial_path = find_data_file(spatial_file)
        base_path = find_data_file(base_file)

        if not spatial_path:
            logger.warning("Spatial data not found: %s", spatial_file)
            continue
        if not base_path:
            logger.warning("Base data not found: %s", base_file)
            continue

        logger.info("Loading floor %d: %s + %s", floor_num, spatial_path, base_path)

        spatial_data = load_json(spatial_path)
        base_data = load_json(base_path)

        nodes = merge_floor_data(spatial_data, base_data, floor_num)
        all_nodes.extend(nodes)
        floors_found.append(floor_num)

        logger.info(
            "  Floor %d: %d nodes (%d rooms, %d junctions)",
            floor_num,
            len(nodes),
            sum(1 for n in nodes if n["type"] != "junction"),
            sum(1 for n in nodes if n["type"] == "junction"),
        )

    if not all_nodes:
        logger.error("No data found. Check data file paths.")
        return

    doc = {
        "building_name": BUILDING_NAME,
        "floors": sorted(floors_found),
        "nodes": all_nodes,
    }

    version = await graphRepository.save_graph(BUILDING_ID, doc, updated_by="graph_seed")

    logger.info(
        "Seeded %s: %d nodes across floors %s (version %d)",
        BUILDING_ID,
        len(all_nodes),
        sorted(floors_found),
        version,
    )


async def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    await seed()


if __name__ == "__main__":
    asyncio.run(main())
