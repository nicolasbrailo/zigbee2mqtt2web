"""
TTS helpers: given a phrase, attempt to create a local sound file
"""
import datetime
import hashlib
import os
import urllib.request

from pathlib import Path
from urllib.parse import quote
from zzmw_lib.service_runner import build_logger

log = build_logger("MqttSpeakerAnnounceTTS")

def _delete_old_files(directory, days_threshold):
    try:
        threshold_date = datetime.datetime.now() - datetime.timedelta(days=days_threshold)
        files = os.listdir(directory)
        for file in files:
            file_path = os.path.join(directory, file)

            if os.path.isfile(file_path):
                last_modified_time = datetime.datetime.fromtimestamp(os.path.getmtime(file_path))

                if last_modified_time < threshold_date:
                    os.remove(file_path)
                    log.debug('Cleanup old TTS asset %s', file_path)

    except (OSError, ValueError, OverflowError):
        log.error('Failed to cleanup old TTS assets', exc_info=True)

def get_local_path_tts(cache_path, phrase, lang):
    """ Try to get a TTS from Google translate """
    # Try to create cache path, throw on fail
    Path(cache_path).mkdir(parents=True, exist_ok=True)
    _delete_old_files(cache_path, days_threshold=7)

    # Get a url, and the local path to the cache
    url_base = 'https://translate.google.com/translate_tts?client=tw-ob&tl={lang}&q={phrase}'
    url = url_base.format(lang=lang, phrase=quote(phrase))
    cache_fname = hashlib.md5(url.encode('utf-8')).hexdigest() + '.mp3'
    cached = Path(os.path.join(cache_path, cache_fname))

    log.info('TTS requested lang "%s" phrase "%s"', lang, phrase)
    if not cached.is_file():
        log.info('Phrase not cached, need to download...')
        try:
            with urllib.request.urlopen(url) as req:
                with open(cached, 'wb') as cache_f:
                    cache_f.write(req.read())
        except urllib.error.HTTPError as ex:
            raise RuntimeError(
                f'Failed to retrieve TTS from {url}: {str(ex)}') from ex

        if not cached.is_file():
            raise RuntimeError(f"TTS failed: can't download {url}")

    return cache_fname
