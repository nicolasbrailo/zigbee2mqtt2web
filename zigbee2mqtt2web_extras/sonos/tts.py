from urllib.parse import quote
import hashlib
import os
import urllib.request
from pathlib import Path

import logging
logger = logging.getLogger(__name__)

def get_local_path_tts(cache_path, phrase, lang):
    # Try to create cache path, throw on fail
    Path(cache_path).mkdir(parents=True, exist_ok=True)

    # Get a url, and the local path to the cache
    url_base = 'http://translate.google.com/translate_tts?client=tw-ob&tl={lang}&q={phrase}'
    url = url_base.format(lang=lang, phrase=quote(phrase))
    cache_fname = hashlib.md5(url.encode('utf-8')).hexdigest() + '.mp3'
    cached = Path(os.path.join(cache_path, cache_fname))

    logger.info('TTS requested %s phrase %s', lang, phrase)
    if not cached.is_file():
        logger.info('Phrase not cached, need to download...')

        try:
            req = urllib.request.urlopen(url)
            with open(cached, 'wb') as cache_f:
                cache_f.write(req.read())
        except urllib.error.HTTPError as ex:
            raise RuntimeError(f'Failed to retrieve TTS from {url}: {str(ex)}')

        if not cached.is_file():
            raise RuntimeError(f"TTS failed: can't download {url}")

    return cache_fname
