import os
import tempfile
import subprocess

def _run_cmd(cmd):
    stdout = tempfile.TemporaryFile(mode='w+')
    stderr = tempfile.TemporaryFile(mode='w+')
    proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
    return proc, stdout, stderr


def rtsp_to_local_file(rtsp_url, outpath):
    return _run_cmd(["ffmpeg",
                     "-i", rtsp_url,
                     # Copy incoming streams, otherwise ffmpeg will try to reencode (and spend tons of cpu)
                     "-c:v", "copy", "-c:a", "copy",
                     outpath])


def reencode_to_telegram_vid(fpath, reencode_out_file):
    return _run_cmd(["ffmpeg",
                     "-i", fpath,
                     # Eg to reencode @ 720p
                     # "-vf", "scale=-1:720",
                     # Telegram format
                     "-vf", "scale=640:360",
                     "-c:v", "libx264",
                     "-crf", "23",
                     "-preset", "veryfast",
                     "-c:a", "copy",
                     reencode_out_file,
                     ])


def gen_thumbnail_from_video(fpath):
    if type(fpath) != str or not fpath.endswith('.mp4'):
        log.error("Requested thumbnail for non-move %s", fpath)
        return None

    fout = f'{fpath}.thumb.png'
    if os.path.exists(fout):
        return fout

    _run_cmd(['ffmpeg',
              '-i', fpath,
              '-vf', 'select=eq(n\,42)',
              '-vf', 'scale=192:168',
              '-vframes', '1',
              fout])
    return fout

