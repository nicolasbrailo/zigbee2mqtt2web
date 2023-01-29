"""
Creates an FTP server. This server relies on an external firewall, and if anything fishy is detected (eg an unknown
IP or user trying to connect) it will crash the process, and create a token file so that it will never start again (it
will crash loop if started as a system service).
"""

import os
import threading
from pyftpdlib import servers
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.authorizers import DummyAuthorizer

import logging
logger = logging.getLogger(__name__)

# Comment out to see raw FTP commands
logging.getLogger('pyftpdlib').setLevel(logging.ERROR)

""" If a security breach is detected (such as a bad login attempt, or a connection
from a not-allowlisted IP) then the server will crash, and a file will be created
so that the server keeps crashing when started. """
FTP_SECURITY_BAD_FNAME = 'FTP_SECURITY_BAD'


def _die_if_security_risk(marker_path):
    if os.path.exists(os.path.join(marker_path, FTP_SECURITY_BAD_FNAME)):
        # Use logger.error instead of fatal|critical, to ensure we call abort() instead of
        # maybe throwing an exception from the logger
        logger.error('A security issue has been detected, please disable FTP')
        os.abort()


def _not_allowed_connection_detected(marker_path, ip):
    marker = os.path.join(marker_path, FTP_SECURITY_BAD_FNAME)
    f = open(marker, "w")
    f.write(f'Unauthorized connection from {ip} detected\n')
    f.close()
    _die_if_security_risk(marker_path)


def _make_handler(this):
    class FtpHandler(FTPHandler):
        def on_connect(self):
            this.on_connect(self, self.remote_ip)

        def on_disconnect(self):
            this.on_disconnect(self, self.remote_ip)

        def on_login(self, usr):
            this.on_login(self)

        def on_file_received(self, fpath):
            this.on_file_received(self, self.remote_ip, fpath)
    return FtpHandler


class Ftpd:
    def __init__(self, cfg):
        self._bg = None
        self._cfg = cfg
        _die_if_security_risk(self._cfg['ftp_tainted_marker_path'])

        if not os.path.isdir(cfg['upload_local_path']):
            raise IOError(
                f"Can't find FTP upload directory at {cfg['upload_local_path']}")

        if not os.path.isdir(cfg['ftp_tainted_marker_path']):
            raise IOError(
                f"Can't find FTP tainted marker path at {cfg['ftp_tainted_marker_path']}")

        if cfg['upload_local_path'] == cfg['ftp_tainted_marker_path']:
            raise IOError(
                f"FTP tainted marker ({cfg['ftp_tainted_marker_path']}) shouldn't be the "
                f"same as the FTP upload path ({cfg['upload_local_path']})")

        # Ensure we have a list of allowlisted IPs
        if cfg['ip_allowlist'] is None:
            raise RuntimeError('FTP requires a list of allowlisted IPs')

        handler = _make_handler(self)
        handler.authorizer = DummyAuthorizer()
        handler.authorizer.add_user(
            cfg['user'],
            cfg['pwd'],
            cfg['upload_local_path'],
            perm='elradfmwMT')
        self._server = servers.ThreadedFTPServer(
            (cfg['ip'], cfg['port']), handler)

    def _check_allowlisted(underlying_func):
        def wrapper(self, handler, *k, **kw):
            if handler.remote_ip not in self._cfg['ip_allowlist']:
                _not_allowed_connection_detected(
                    self._cfg['ftp_tainted_marker_path'], handler.remote_ip)
            return underlying_func(self, *k, **kw)
        return wrapper

    def start(self):
        """ Run FTPD """
        logger.info(
            'FTPD will listen at %s:%s',
            self._cfg['ip'],
            self._cfg['port'])
        logger.info('Allowlisted IPs: %s', self._cfg['ip_allowlist'])
        self._bg = threading.Thread(target=self._server.serve_forever)
        self._bg.start()

    def stop(self):
        """ Stop FTPD and wait for shutdown """
        self._server.close_all()
        self._bg.join()

    @_check_allowlisted
    def on_connect(self, remote_ip):
        logger.info('FTP client %s connected', remote_ip)

    @_check_allowlisted
    def on_disconnect(self, remote_ip):
        logger.info('FTP client %s disconnected', remote_ip)

    @_check_allowlisted
    def on_login(self):
        pass

    @_check_allowlisted
    def on_file_received(self, remote_ip, fpath):
        logger.info('FTP client %s uploaded file %s', remote_ip, fpath)
        self._on_upload_complete(remote_ip, fpath)

    def _on_upload_complete(self, remote_ip, fpath):
        raise RuntimeError('Subclass responsibility')
