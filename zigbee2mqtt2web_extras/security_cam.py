""" FTP server for a security cam: sends a Whatsapp notification on file upload """

import os
from .utils.ftpd import Ftpd

import logging
logger = logging.getLogger(__name__)


class SecurityCam(Ftpd):
    """ Creates an FTPD. This class expects the camera to upload a picture when motion starts,
    and then a video once the motion ends """

    def __init__(self, cfg, wa):
        self._cam_ips = cfg['cam_ips']
        self._wa_notify = cfg['wa_notify']
        self._motion_detected_clients = {}
        self._wa = wa
        cfg['ftp']['ip_allowlist'] = self._cam_ips
        Ftpd.__init__(self, cfg['ftp'])

    def _on_upload_complete(self, remote_ip, fpath):
        _, ext = os.path.splitext(fpath)
        ext = ext[1:]
        if ext == 'mp4':
            self._motion_cleared(remote_ip, fpath)
            return
        if ext in ['jpg', 'jpeg']:
            self._motion_detected(remote_ip, fpath)
            return
        print(f'Error: client {remote_ip} uploaded unknown file type {fpath}')

    def _motion_detected(self, remote_ip, fpath):
        # TODO timeout
        if remote_ip in self._motion_detected_clients and self._motion_detected_clients[
                remote_ip]:
            print(f'Client {remote_ip} sent update, but alarm already on')
            return

        # TODO log time for timeout
        self._motion_detected_clients[remote_ip] = True
        media_id = self._wa.upload_image(fpath)
        for num in self._wa_notify:
            print(f'Client {remote_ip} uploaded {fpath}, alert {num}')
            self._wa.message_from_params_template(num, media_id)

    def _motion_cleared(self, remote_ip, fpath):
        # TODO log time for timeout
        self._motion_detected_clients[remote_ip] = False
        print(f'Client {remote_ip} uploaded {fpath}, alert clear')
