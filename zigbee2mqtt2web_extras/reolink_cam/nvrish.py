import os
from datetime import datetime, timedelta
from flask import send_from_directory

from .ffmpeg_helper import gen_thumbnail_from_video


def _get_cams(base_path):
    cams = []
    for entry in os.listdir(base_path):
        full_path = os.path.join(base_path, entry)
        if os.path.isdir(full_path):
            cams.append(entry)
    return cams


def _format_file_size(sz):
    if sz < 1024:
        return f"{sz} bytes"
    elif sz < 1024 * 1024:
        return f"{sz / 1024:.0f} KB"
    else:
        return f"{sz / (1024 * 1024):.0f} MB"

def _get_month_name(month_number):
    month_names = [
        "January", "February", "March", "April",
        "May", "June", "July", "August",
        "September", "October", "November", "December"
    ]
    # Adjust month_number to match the index of month_names
    index = month_number - 1
    return month_names[index] if 1 <= month_number <= 12 else f"Month {month_number}?"

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


def _parse_and_format_filename(filename):
    try:
        datetime_str = filename.split('.')[0]
        date = datetime_str.split('_')[0]
        hour = datetime_str.split('_')[1]
        month = int(datetime_str[4:6])
        day = int(datetime_str[6:8])
        hr = int(hour[0:2])
        minute = int(hour[2:4])
        return f'{_get_month_name(month)} - {day:02} - {hr:02}:{minute:02}'
    except:
        return filename


_GALLERY_STYLE = """
<link rel="stylesheet" href="/www/rel.css">
<style>
img {
  display: block;
}
li {
  list-style: none;
  display: inline-block;
  border: 1px solid grey;
}
</style>
"""

def _nvr_template(base_path, txt):
    cams_html = '<ul>'
    for cam in _get_cams(base_path):
        cams_html = f'<li><a href="/nvr/{cam}/files">{cam}</a></li>'
    cams_html += '</ul>'

    return _GALLERY_STYLE + cams_html + txt

class Nvr:
    def __init__(self, nvr_path):
        self._nvr_path = nvr_path
        self._cams = []
        self._cam_files = {}
        self._default_gallery_history_days = 3

    def _list_cams(self):
        txt = ""
        for cam in _get_cams(self._nvr_path):
            txt += f'<li><a href="/nvr/{cam}/files">{cam}</a></li>'
        return txt

    def _list_cam_recs(self, cam):
        path, recs = _get_cam_recordings(self._nvr_path, cam)

        if path is None:
            return  f"Unknown cam {cam}", 404

        txt = ""
        for (fname, fpath, fsize, ftime) in recs:
            txt += f'<li><a href="/nvr/{cam}/get_recording/{fname}">{_parse_and_format_filename(fname)} - {fsize}</a></li>'
        return txt

    def _list_cam_recs_as_gallery(self, cam):
        return self._list_cam_recs_as_gallery_days(cam, self._default_gallery_history_days)

    def _list_cam_recs_as_gallery_days(self, cam, days):
        if type(days) != int and not days.isdigit():
            return f"Days must be a number, received {days}", 400

        path, recs = _get_cam_recordings(self._nvr_path, cam, int(days))
        if path is None:
            return  f"Unknown cam {cam}", 404

        txt = _GALLERY_STYLE
        for (fname, fpath, fsize, ftime) in recs:
            img_path = gen_thumbnail_from_video(fpath)
            img_fname = os.path.basename(img_path)
            img_url = f"/nvr/{cam}/get_recording/{img_fname}"
            img = f'<img src="{img_url}"/>'
            txt += f'<li><a href="/nvr/{cam}/get_recording/{fname}">{img}{_parse_and_format_filename(fname)} - {fsize}</a></li>'
        return _nvr_template(self._nvr_path, txt)

    def _get_recording(self, cam, file):
        path = os.path.join(self._nvr_path, cam)
        if not os.path.exists(path) or not os.path.isdir(path):
            return f"Can't get recording for unknown cam {cam}", 404

        fpath = os.path.join(path, file)
        if not os.path.exists(fpath) or not os.path.isfile(fpath):
            return f"Can't get unknown recording {file} for unknown cam {cam}", 404

        return send_from_directory(path, file)

