#!/usr/bin/env python3
"""
Utility to merge all config.json files from subdirectories into one config_all.json.

Each sub-config is stored under a key matching its directory name.
"""

import json
from pathlib import Path


def find_configs(base_path: Path) -> list[Path]:
    """Find all config.json files recursively."""
    return sorted(base_path.rglob("config.json"))


def merge_configs(config_paths: list[Path], base_path: Path) -> dict:
    """Merge all configs into one dict, keyed by directory name."""
    merged = {}
    for config_path in config_paths:
        relative = config_path.relative_to(base_path)
        key = str(relative.parent)
        if key == ".":
            key = "root"
        with open(config_path) as f:
            merged[key] = json.load(f)
    return merged


def main():
    base_path = Path.cwd()
    config_paths = find_configs(base_path)

    if not config_paths:
        print("No config.json files found.")
        return

    print(f"Found {len(config_paths)} config.json file(s):")
    for path in config_paths:
        print(f"  - {path.relative_to(base_path)}")

    print()
    input("Press Enter to continue (Ctrl+C to cancel)... ")

    merged = merge_configs(config_paths, base_path)
    output_path = base_path / "config_all.json"

    with open(output_path, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Merged config written to {output_path}")


if __name__ == "__main__":
    main()
