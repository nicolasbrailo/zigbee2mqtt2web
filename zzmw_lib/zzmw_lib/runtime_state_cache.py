"""Runtime state cache for persisting service state between restarts."""
import json

CACHE_FILE = "run_state_cache.json"
CACHE_COMMENT = "This file is a cache to persist service run state between restarts, it can be safely deleted"


def runtime_state_cache_get(key):
    """
    Get a value from the runtime state cache.

    Args:
        key: The key to retrieve from the cache

    Returns:
        The cached value, or None if the key doesn't exist or the file is missing/corrupt
    """
    try:
        with open(CACHE_FILE) as f:
            return json.load(f).get(key)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def runtime_state_cache_set(key, value):
    """
    Set a value in the runtime state cache.

    Reads the existing cache file (or creates an empty one with a comment),
    then saves the new key-value pair.

    Args:
        key: The key to set
        value: The value to store
    """
    try:
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        cache = {"COMMENT": CACHE_COMMENT}

    cache[key] = value
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)
