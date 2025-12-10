"""Helper functions for Sonos speaker discovery and configuration."""
import logging
from soco import discover

def config_soco_logger(use_debug_log):
    """Configure logging level for soco library."""
    if not use_debug_log:
        logging.getLogger('soco.*').setLevel(logging.INFO)
        logging.getLogger('soco.core').setLevel(logging.INFO)
        logging.getLogger('soco.services').setLevel(logging.INFO)
        logging.getLogger('soco.discovery').setLevel(logging.INFO)
        logging.getLogger('soco.zonegroupstate').setLevel(logging.INFO)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)


def get_sonos_by_name():
    """ Returns a map of all LAN Sonos players """
    all_sonos = {}
    for player_obj in discover():
        all_sonos[player_obj.player_name] = player_obj
    return all_sonos
