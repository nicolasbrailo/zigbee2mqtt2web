"""NVR-ish web interface for camera recordings."""
import os
from datetime import datetime, timedelta
from flask import send_from_directory, jsonify, redirect, request
from ffmpeg_helper import gen_thumbnail_from_video

def _get_cams(base_path):
    if not os.path.exists(base_path) or not os.path.isdir(base_path):
        return []
    cams = []
    for entry in os.listdir(base_path):
        full_path = os.path.join(base_path, entry)
        if os.path.isdir(full_path):
            cams.append(entry)
    return cams


def _format_file_size(sz):
    if sz < 1024:
        return f"{sz} bytes"
    if sz < 1024 * 1024:
        return f"{sz / 1024:.0f} KB"
    return f"{sz / (1024 * 1024):.0f} MB"

def _get_cam_recordings(base_path, cam, days=None):
    path = os.path.join(base_path, cam)
    if not os.path.exists(path) or not os.path.isdir(path):
        return None, None

    ftimelimit = None
    if days is not None:
        ftimelimit = datetime.today() - timedelta(days=days)
    recs = []
    for root, _, filenames in os.walk(path):
        for fname in filenames:
            fpath = os.path.join(root, fname)
            fsize = os.path.getsize(fpath)
            fsize = _format_file_size(fsize)
            ftime = os.path.getmtime(fpath)

            is_in_requested_time = ftimelimit is None or datetime.fromtimestamp(ftime) > ftimelimit
            is_movie = fname.endswith('.mp4')
            if is_in_requested_time and is_movie:
                recs.append((fname, fpath, fsize, ftime))
    recs.sort(reverse=True)
    return path, recs



class Nvr:
    """Web interface for browsing and viewing camera recordings."""
    def __init__(self, nvr_path, flask_app):
        self._nvr_path = nvr_path

        # Redirect /nvr to the React app
        flask_app.add_url_rule('/nvr', None, lambda: redirect('/nvr.html'))
        flask_app.add_url_rule('/nvr/api/cameras', None, self._api_list_cams)
        flask_app.add_url_rule('/nvr/api/<cam>/recordings', None, self._api_list_recordings)
        flask_app.add_url_rule('/nvr/<cam>/get_recording/<file>', None, self._get_recording)

    def _api_list_cams(self):
        """Return JSON list of available cameras."""
        cameras = _get_cams(self._nvr_path)
        return jsonify({'cameras': cameras})

    def _api_list_recordings(self, cam):
        """Return JSON list of recordings for a camera."""
        # Get days parameter from query string (default to all if not specified)
        days = request.args.get('days', type=int)
        if days == 0:
            days = None  # 0 means show all recordings

        path, recs = _get_cam_recordings(self._nvr_path, cam, days)

        if path is None:
            return jsonify({'error': f'Unknown camera {cam}'}), 404

        recordings = []
        for (fname, fpath, fsize, _) in recs:
            # Generate thumbnail
            img_path = gen_thumbnail_from_video(fpath)
            if img_path is None:
                thumbnail_url = None
            else:
                img_fname = os.path.basename(img_path)
                thumbnail_url = f'/nvr/{cam}/get_recording/{img_fname}'

            recordings.append({
                'filename': fname,
                'size': fsize,
                'video_url': f'/nvr/{cam}/get_recording/{fname}',
                'thumbnail_url': thumbnail_url
            })

        return jsonify({'recordings': recordings})

    def _get_recording(self, cam, file):
        path = os.path.join(self._nvr_path, cam)
        if not os.path.exists(path) or not os.path.isdir(path):
            return f"Can't get recording for unknown cam {cam}", 404

        fpath = os.path.join(path, file)
        if not os.path.exists(fpath) or not os.path.isfile(fpath):
            return f"Can't get unknown recording {file} for unknown cam {cam}", 404

        return send_from_directory(path, file)
