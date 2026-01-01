"""FFmpeg helper functions for RTSP recording and reencoding."""
import os
import tempfile
import subprocess

from zzmw_lib.logs import build_logger
log = build_logger("FFmpegHelper")

def _run_cmd(cmd):
    stdout = tempfile.TemporaryFile(mode='w+')
    stderr = tempfile.TemporaryFile(mode='w+')
    try:
        proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
    except OSError as e:
        # OSError covers FileNotFoundError, PermissionError, and other OS-level failures
        log.error("Failed to run command %s: %s", cmd[0] if cmd else "<empty>", e)
        stdout.close()
        stderr.close()
        return None, None, None
    return proc, stdout, stderr


def rtsp_to_local_file(rtsp_url, outpath):
    """Start recording from RTSP stream to local file."""
    return _run_cmd(["ffmpeg",
                     "-i", rtsp_url,
                     # Copy incoming streams, otherwise ffmpeg will try to reencode (and spend tons of cpu)
                     "-c:v", "copy", "-c:a", "copy",
                     outpath])


def reencode_to_telegram_vid(fpath, reencode_out_file):
    """Reencode video to Telegram-compatible format (640x360 x264)."""
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
    """Generate a thumbnail image from video file."""
    if not isinstance(fpath, str) or not fpath.endswith('.mp4'):
        log.error("Requested thumbnail for non-move %s", fpath)
        return None

    fout = f'{fpath}.thumb.png'
    if os.path.exists(fout):
        return fout

    proc, _, _ = _run_cmd(['ffmpeg',
                           '-i', fpath,
                           '-vf', 'select=eq(n,42)',
                           '-vf', 'scale=192:168',
                           '-vframes', '1',
                           fout])
    if proc is None:
        return None
    return fout
