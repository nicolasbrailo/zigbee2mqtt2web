#!/usr/bin/env python3
"""
Utility to manage config.json files across all service subfolders.

Usage:
    ./config_update.py --collect     # Collect all sub-configs into unified config.json
    ./config_update.py --distribute  # Distribute unified config.json to sub-configs
"""

import argparse
import json
import sys
from pathlib import Path


UNIFIED_CONFIG_FILE = "config.json"
COMMON_KEY = "_common"
COMMON_FIELDS = ["mqtt_ip", "mqtt_port"]
JUNK_KEYS = ["JSON IS", "JSON"]  # Trailing comma workaround keys to remove


def get_script_dir() -> Path:
    """Get the directory where this script is located."""
    return Path(__file__).parent.resolve()


def find_sub_configs(base_dir: Path) -> dict[str, Path]:
    """Find all config.json files in immediate subdirectories."""
    sub_configs = {}
    for subdir in sorted(base_dir.iterdir()):
        if subdir.is_dir():
            config_path = subdir / "config.json"
            if config_path.exists():
                sub_configs[subdir.name] = config_path
    return sub_configs


def remove_junk_keys(config: dict) -> dict:
    """Remove trailing comma workaround keys from config."""
    return {k: v for k, v in config.items() if k not in JUNK_KEYS}


def extract_common_fields(config: dict) -> tuple[dict, dict]:
    """Extract common fields from config, returning (common, remaining)."""
    common = {}
    remaining = {}
    for k, v in config.items():
        if k in COMMON_FIELDS:
            common[k] = v
        else:
            remaining[k] = v
    return common, remaining


def collect_configs(base_dir: Path) -> None:
    """Collect all sub-configs into a single unified config.json."""
    sub_configs = find_sub_configs(base_dir)

    if not sub_configs:
        print("No config.json files found in subdirectories.")
        sys.exit(1)

    # First pass: load all configs and extract common fields
    loaded = {}
    common_values = {}  # field -> {value -> [services]}

    for service_name, config_path in sub_configs.items():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            config = remove_junk_keys(config)
            loaded[service_name] = config
            print(f"  Collected: {service_name}")

            # Track common field values
            for field in COMMON_FIELDS:
                if field in config:
                    value = config[field]
                    if field not in common_values:
                        common_values[field] = {}
                    value_key = json.dumps(value)  # Handle non-hashable values
                    if value_key not in common_values[field]:
                        common_values[field][value_key] = []
                    common_values[field][value_key].append(service_name)

        except json.JSONDecodeError as e:
            print(f"  Error parsing {config_path}: {e}")
            sys.exit(1)

    # Check for conflicting common values
    common_section = {}
    for field in COMMON_FIELDS:
        if field in common_values:
            values = common_values[field]
            if len(values) > 1:
                print(f"\nError: Conflicting values for '{field}':")
                for value_key, services in values.items():
                    value = json.loads(value_key)
                    print(f"  {value}: {', '.join(services)}")
                sys.exit(1)
            # All services have the same value
            value_key = list(values.keys())[0]
            common_section[field] = json.loads(value_key)

    # Build unified config with common section first
    unified = {COMMON_KEY: common_section}

    for service_name, config in loaded.items():
        _, remaining = extract_common_fields(config)
        # Also remove mqtt_comment since it's related to common fields
        remaining.pop("mqtt_comment", None)
        unified[service_name] = remaining

    unified_path = base_dir / UNIFIED_CONFIG_FILE
    with open(unified_path, "w") as f:
        json.dump(unified, f, indent=2)
        f.write("\n")

    print(f"\nCreated unified config with {len(loaded)} services: {unified_path}")
    print(f"Common settings: {common_section}")


def distribute_configs(base_dir: Path) -> None:
    """Distribute unified config.json to individual sub-configs."""
    unified_path = base_dir / UNIFIED_CONFIG_FILE

    if not unified_path.exists():
        print(f"Unified config not found: {unified_path}")
        print("Run with --collect first to create it.")
        sys.exit(1)

    try:
        with open(unified_path, "r") as f:
            unified = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error parsing {unified_path}: {e}")
        sys.exit(1)

    # Extract common section
    common_section = unified.pop(COMMON_KEY, {})
    if not common_section:
        print("Warning: No _common section found in unified config")

    updated = 0
    created = 0
    for service_name, config_data in unified.items():
        subdir = base_dir / service_name
        config_path = subdir / "config.json"

        if not subdir.exists():
            print(f"  Skipping {service_name}: directory does not exist")
            continue

        # Prepend common fields to the config
        full_config = {**common_section, **config_data}

        existed = config_path.exists()
        with open(config_path, "w") as f:
            json.dump(full_config, f, indent=2)
            f.write("\n")

        if existed:
            print(f"  Updated: {service_name}")
            updated += 1
        else:
            print(f"  Created: {service_name}")
            created += 1

    print(f"\nDistributed config: {updated} updated, {created} created")
    print(f"Common settings applied: {common_section}")


def main():
    parser = argparse.ArgumentParser(
        description="Manage config.json files across service subfolders."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-c", "--collect",
        action="store_true",
        help="Collect all sub-configs into a unified config.json"
    )
    group.add_argument(
        "-d", "--distribute",
        action="store_true",
        help="Distribute unified config.json to sub-configs"
    )

    args = parser.parse_args()
    base_dir = get_script_dir()

    if args.collect:
        print("Collecting configs from subdirectories...")
        collect_configs(base_dir)
    elif args.distribute:
        print("Distributing config to subdirectories...")
        distribute_configs(base_dir)


if __name__ == "__main__":
    main()
