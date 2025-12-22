#!/usr/bin/env python3
"""
Apply a merged config file back to individual directory config.json files.

Usage:
    ./config_apply.py config_all.json
"""

import json
import sys
from pathlib import Path


def load_merged_config(config_path: Path) -> dict:
    """Load the merged config file."""
    with open(config_path) as f:
        return json.load(f)


def get_config_path(base_path: Path, key: str) -> Path:
    """Get the config.json path for a given key."""
    if key == "root":
        return base_path / "config.json"
    return base_path / key / "config.json"


def get_directory_path(base_path: Path, key: str) -> Path:
    """Get the directory path for a given key."""
    if key == "root":
        return base_path
    return base_path / key


def validate_structure(merged_config: dict, base_path: Path) -> bool:
    """Validate that all keys match directories and all directories have entries."""
    keys = set(merged_config.keys())

    # Find all directories that have config.json
    existing_configs = set()
    for config_path in base_path.rglob("config.json"):
        relative = config_path.relative_to(base_path)
        key = str(relative.parent)
        if key == ".":
            key = "root"
        existing_configs.add(key)

    # Check for keys without directories
    missing_dirs = keys - existing_configs
    if missing_dirs:
        for key in sorted(missing_dirs):
            dir_path = get_directory_path(base_path, key)
            config_path = get_config_path(base_path, key)
            if not dir_path.is_dir():
                print(f"Error: Key '{key}' has no matching directory: {dir_path}")
            elif not config_path.exists():
                print(f"Error: Directory '{key}' has no config.json: {config_path}")
        return False

    # Check for directories without entries
    missing_keys = existing_configs - keys
    if missing_keys:
        for key in sorted(missing_keys):
            print(f"Error: Directory '{key}' has config.json but no entry in merged config")
        return False

    return True


def find_differences(merged_config: dict, base_path: Path) -> list[str]:
    """Find keys where the merged config differs from the existing config."""
    differences = []
    for key, new_content in merged_config.items():
        config_path = get_config_path(base_path, key)
        with open(config_path) as f:
            existing_content = json.load(f)
        if existing_content != new_content:
            differences.append(key)
    return sorted(differences)


def apply_configs(merged_config: dict, base_path: Path, keys: list[str]):
    """Apply the merged config to the specified keys."""
    for key in keys:
        config_path = get_config_path(base_path, key)
        with open(config_path, "w") as f:
            json.dump(merged_config[key], f, indent=2)
        print(f"  Updated: {config_path.relative_to(base_path)}")


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <merged_config.json>")
        sys.exit(1)

    merged_config_path = Path(sys.argv[1])
    if not merged_config_path.exists():
        print(f"Error: File not found: {merged_config_path}")
        sys.exit(1)

    base_path = Path.cwd()
    merged_config = load_merged_config(merged_config_path)

    if not merged_config:
        print("Error: Merged config is empty")
        sys.exit(1)

    print(f"Loaded {len(merged_config)} entries from {merged_config_path}")

    if not validate_structure(merged_config, base_path):
        sys.exit(1)

    differences = find_differences(merged_config, base_path)

    if not differences:
        print("All configs are already up to date.")
        return

    print(f"\n{len(differences)} config(s) will be updated:")
    for key in differences:
        config_path = get_config_path(base_path, key)
        print(f"  - {config_path.relative_to(base_path)}")

    print()
    input("Press Enter to apply changes (Ctrl+C to cancel)... ")

    apply_configs(merged_config, base_path, differences)
    print(f"\nDone. Updated {len(differences)} config(s).")


if __name__ == "__main__":
    main()
