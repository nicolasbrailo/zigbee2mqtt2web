from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
from threading import Lock
import logging
import os
import signal
import subprocess
import tempfile

log = logging.getLogger(__name__)


def _run_cmd(cmd):
    stdout = tempfile.TemporaryFile(mode='w+')
    stderr = tempfile.TemporaryFile(mode='w+')
    proc = subprocess.Popen(cmd, stdout=stdout, stderr=stderr)
    return proc, stdout, stderr


def _stop_cmd(log_prefix, timeout, force_log_out, proc, stdout, stderr):
    proc.send_signal(signal.SIGINT)
    proc.wait(timeout)

    if proc.poll() is None:
        log.error("%s: failed to stop in time, killing...", log_prefix)
        proc.terminate()

    if proc.returncode != 0:
        log.error("%s failed, ret=%s", log_prefix, proc.returncode)

    # if proc.returncode != 0 or 
    # ffmpeg may return non zero even if it succeeded
    if force_log_out:
        stdout.seek(0)
        log.error("%: ******* stdout start ******", log_prefix)
        for ln in stdout.read().split('\n'):
            log.error(ln)

        stderr.seek(0)
        log.error("%: ******* stderr start ******", log_prefix)
        for ln in stderr.read().split('\n'):
            log.error(ln)

    stdout.close()
    stderr.close()


def _delete_old_files(directory, days_threshold):
    try:
        threshold_date = datetime.now() - timedelta(days=days_threshold)
        files = os.listdir(directory)
        for file in files:
            file_path = os.path.join(directory, file)

            if os.path.isfile(file_path):
                last_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))

                if last_modified_time < threshold_date:
                    os.remove(file_path)
                    log.debug('Cleanup old NVR asset %s', file_path)

    except Exception as e:
       log.error('Failed to cleanup old NVR assets', exc_info=True)


class Rtsp:
    """ Manage RTSP recordings """
    def __init__(self, cam_host, system_event_cb, rec_path_prefix, retention_days=15, default_duration_secs=10):
        self._scheduler = BackgroundScheduler()
        self._scheduler.start()

        self._default_recording_duration_secs = default_duration_secs
        self._process_stop_timeout_secs = 5
        self._reencode_timeout_secs = 20
        self._cam_host = cam_host
        self._announce_event = system_event_cb

        # TODO get rtsp from cam
        self._rtsp_url = "rtsp://admin:@10.10.30.20:554/h264Preview_01_main"

        if not os.path.exists(rec_path_prefix):
            log.error("Cam %s: recording path not available at %s (missing external drive?)", cam_host, rec_path_prefix)
            self._outdir = None
        else:
            self._nvr_retention_days = retention_days
            self._outdir = os.path.join(rec_path_prefix, cam_host)
            if not os.path.exists(self._outdir):
                os.makedirs(self._outdir)
            log.info("Cam %s: RTSP recordings will be saved at %s", cam_host, self._outdir)

        self._update_lock = Lock()
        self._recording_job_updating = False
        self._recording_job = None
        self._recording_cmd = None
        self.recording_cmd_stdout = None
        self.recording_cmd_stderr = None
        self._recording_duration = None
        self._recording_outfile = None
        self._last_recording_fpath = None


    def _cb_on_new_recording(self, outfile):
        log.info("Cam %s: New RTSP recording at %s", self._cam_host, outfile)
        self._announce_event({
            'event': 'on_cam_recording_available',
            'doorbell_cam': self._cam_host,
            'fpath': outfile,
            'fname': os.path.basename(outfile),
        })

    def _cb_on_recording_failed(self, outfile):
        log.error("Cam %s: RTSP failed to record %s", self._cam_host, outfile)
        self._announce_event({
            'event': 'on_cam_recording_failed',
            'doorbell_cam': self._cam_host,
            'fpath': outfile,
            'fname': os.path.basename(outfile),
        })

    def _cb_on_reencoding_ok(self, src, reencoded):
        log.info("Cam %s: Reencoding of %s at %s", self._cam_host, src, reencoded)
        self._announce_event({
            'event': 'on_cam_recording_reencoded',
            'doorbell_cam': self._cam_host,
            'fpath': reencoded,
            'original_fpath': src,
            'original_fname': os.path.basename(src),
        })

    def _cb_on_reencoding_failed(self, src):
        log.error("Cam %s: Failed to reencode %s", self._cam_host, src)
        self._announce_event({
            'event': 'on_cam_recording_reencoding_failed',
            'doorbell_cam': self._cam_host,
            'fpath': None,
            'original_fpath': src,
            'original_fname': os.path.basename(src),
        })


    def trigger_recording(self, duration_secs=None):
        """ Start a new RTSP recording. If one is ongoing, change the timeout to the new duration """
        if self._outdir is None:
            log.error("Cam %s: recording path not available at %s (missing external drive?)", cam_host, rec_path_prefix)
            return

        recording_duration = duration_secs or self._default_recording_duration_secs
        with self._update_lock:
            # Bail out if we're still launching or tearing down an old RTSP job
            if self._recording_job_updating:
                log.warning("Cam %s: recording job is being set up, can't schedule a new one or reschedule old one", self._cam_host)
                return

            if self._recording_job is not None:
                log.info("Cam %s has ongoing recording. Extending timeout by %s seconds", self._cam_host, recording_duration)
                self._recording_job.reschedule(trigger="date", run_date=(datetime.now() + timedelta(seconds=recording_duration)))
                return

            self._recording_job_updating = True

        # Launch job out of lock, we don't know how long it'll take to spin up
        self._launch_new_recording_job(recording_duration)
        self._recording_job_updating = False


    def _launch_new_recording_job(self, recording_duration):
        log.info("Cam %s: will record for %s seconds", self._cam_host, recording_duration)
        self._recording_outfile = os.path.join(self._outdir, datetime.now().strftime("%Y%m%d_%H%M%S.mp4"))
        self._recording_duration = recording_duration
        self._recording_cmd, \
                self.recording_cmd_stdout, \
                self.recording_cmd_stderr = _run_cmd(["ffmpeg", "-i", self._rtsp_url, self._recording_outfile])

        self._recording_job = self._scheduler.add_job(
            func=self._on_recording_complete,
            trigger="date",
            run_date=(datetime.now() + timedelta(seconds=recording_duration)))


    def _on_recording_complete(self):
        log.info("Cam %s: recording duration reached, stopping RTSP", self._cam_host)
        with self._update_lock:
            self._recording_job_updating = True

        # If file wasn't created, force log output even if ret is success. This relies on
        # ffmpeg creating a file that's visibile before process stop, which may not always
        # be true in all filesystems and may cause false positive failure reporting
        force_log_out = False
        outfile = self._recording_outfile
        if not os.path.exists(outfile):
            log.error("Cam %s: RTSP recording failed, can't find output at %s", outfile, outfile)
            force_log_out = True

        # Work out of lock, we don't know how long it'll take to spin down
        _stop_cmd(f"Cam {self._cam_host}: RTSP", self._process_stop_timeout_secs, force_log_out,
                    self._recording_cmd, self.recording_cmd_stdout, self.recording_cmd_stderr)

        # Clean up state
        self._recording_duration = self._recording_job = self._recording_outfile = \
                self._recording_cmd = self.recording_cmd_stdout = self.recording_cmd_stderr = None

        # Lastly, signal it's safe to start a new process
        self._recording_job_updating = False

        if os.path.exists(outfile):
            self._last_recording_fpath = outfile
            self._cb_on_new_recording(outfile)
        else:
            self._cb_on_recording_failed(outfile)
        _delete_old_files(self._outdir, self._nvr_retention_days)


    def pet_timer(self):
        if self._outdir is None:
            # Recording disabled
            return

        if not self._recording_job:
            log.error("Cam %s: motion reported. Tried to renew timeout, but recording is not active", self._cam_host)
            return

        with self._update_lock:
            log.info("Cam %s has ongoing recording. Extending timeout by %s seconds", self._cam_host, self._recording_duration)
            self._recording_job.reschedule(trigger="date", run_date=(datetime.now() + timedelta(seconds=self._recording_duration)))


    def reencode_for_telegram(self, fpath):
        """ Create a new file based on a previous recording, reencoded for Telegram (x264 640x360) """
        if fpath is None:
            fpath = self._last_recording_fpath

        if fpath is None:
            log.error("Cam %s: Requested reencoding for last recording, but none is known", self._cam_host)
            self._cb_on_reencoding_failed("<last recording unknown>")
            return

        if not os.path.exists(fpath):
            log.error("Cam %s: Requested reencoding of non existing file %s", self._cam_host, fpath)
            self._cb_on_reencoding_failed(fpath)
            return

        reencode_out_file = f"{fpath}.small.mp4"
        if os.path.exists(reencode_out_file):
            self._cb_on_reencoding_ok(fpath, reencode_out_file)
            return

        cmd, stdout, stderr = _run_cmd(["ffmpeg",
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

        def _on_reencoding_timeout():
            _stop_cmd(f"RTSP {fpath} reencode:", self._process_stop_timeout_secs, False, cmd, stdout, stderr)
            if os.path.exists(reencode_out_file):
                self._cb_on_reencoding_ok(fpath, reencode_out_file)
            else:
                self._cb_on_reencoding_failed(fpath)

        self._scheduler.add_job(
                    func=_on_reencoding_timeout,
                    trigger="date",
                    run_date=(datetime.now() + timedelta(seconds=self._reencode_timeout_secs)))

