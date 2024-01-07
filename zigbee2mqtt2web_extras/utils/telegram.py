""" Trivial Telegram wrapper """

from apscheduler.schedulers.background import BackgroundScheduler
import base64
import datetime
import json
import logging
import requests


log = logging.getLogger(__name__)

logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('apscheduler.scheduler').setLevel(logging.ERROR)
logging.getLogger('apscheduler.executors.default').setLevel(logging.ERROR)


# If a message received from the user is longer than this, it will be
# discarded for security
_MAX_USER_MESSAGE_LEN = 100
# If a user command can be split into more than N tokens, discard it for
# security
_MAX_USER_CMD_TOKS = 10


class TelegramApiError(RuntimeError):
    """ The Telegram API responded with something we don't know how to parse, or the
    message sent to Telegram caused an error """
    pass


class TelegramRateLimitError(RuntimeError):
    """ Currently being ratelimited by the API """
    pass


class TelegramHttpError(RuntimeError):
    """ Transport error """
    pass


def _telegram_req(url, params=None, data=None, files=None, post=False):
    try:
        req_method = requests.post if post else requests.get
        req = req_method(url, params=params, data=data, files=files)
        if req.status_code == 429:
            raise TelegramRateLimitError()

        if req.status_code != 200:
            raise TelegramHttpError(
                f'Telegram request {url} failed, status {req.status_code} - {req.reason}')

        jreq = req.json()
        if not jreq['ok']:
            raise TelegramApiError(jreq['description'])

        return jreq['result']
    except requests.exceptions.RequestException as ex:
        raise TelegramHttpError(f'Telegram request {url} failed') from ex


_telegram_get = _telegram_req


def _telegram_post(*a, **kw):
    kw['post'] = True
    return _telegram_req(*a, **kw)


def _validate_telegram_cmds(cmds):
    fmt_cmds = []
    known_commands = {}
    for cmd in cmds:
        try:
            cmd, descr, cb = cmd
        except ValueError as ex:
            raise ValueError(
                f'TelegramBot {cmd} not valid: format should be tuple of (command, description, callback)') from ex

        if cmd in known_commands:
            raise KeyError(f'TelegramBot command {cmd} is duplicated')

        # Allow only alnum and underscores as cmds
        if not cmd.replace('_', '').isalnum():
            raise KeyError(f'TelegramBot command {cmd} is not alphanumeric')

        known_commands[cmd] = cb
        fmt_cmds.append({'command': cmd, 'description': descr})

    return known_commands, str(json.dumps(fmt_cmds))


def _telegram_sanitize_user_message(msg, known_cmds):
    if 'message' not in msg:
        log.debug('Ignoring non message update %s', msg)
        return None

    msg = msg['message']
    if 'from' not in msg or 'chat' not in msg or 'id' not in msg['chat']:
        log.debug(
            "Dropping dangerous looking message, can't find 'from' and 'chat' fields",
            msg)
        return None

    if 'text' not in msg:
        log.debug('Ignoring message/thread metadata update %s', msg)
        return None

    if len(msg['text']) > _MAX_USER_MESSAGE_LEN:
        log.debug(
            'Message from user %s is longer than %s, discarding message',
            msg['from']['first_name'],
            _MAX_USER_MESSAGE_LEN)
        return None

    cmd = None
    cmd_args = None
    if msg['text'][0] == '/':
        # Looks like a command
        toks = msg['text'].split(' ')
        if len(toks) > _MAX_USER_CMD_TOKS:
            log.debug(
                'Command from user %s has more than %s tokens, discarding message',
                msg['from']['first_name'],
                _MAX_USER_CMD_TOKS)
            return None

        cmd = toks[0]
        cmd = cmd[1:]  # Skip initial / of '/cmd'
        if cmd not in known_cmds:
            log.debug(
                'User %s requested unknown command %s, discarding message',
                msg['from']['first_name'],
                cmd)
            return None

        cmd_args = toks[1:]

    # Return only fields that look safe to parse
    return {
        'from': msg['from'],
        'chat': msg['chat'],
        'text': msg['text'],
        'cmd': cmd,
        'cmd_args': cmd_args,
    }


class TelegramBot:
    """ Simple Telegram wrapper to send messages, receive chats, etc """

    def __init__(self, tok):
        """
        Create a Telegram API wrapper.
        Register a bot @ https://telegram.me/BotFather then use the received token here
        """
        self._api_base = f'https://api.telegram.org/bot{tok}'
        self._updates_offset = None
        self._known_commands = {}

        self.bot_info = _telegram_get(f'{self._api_base}/getMe')
        if not self.bot_info['is_bot']:
            log.error(
                "Telegram says the account under control isn't a bot, things may not work")

    def set_bot_name(self, bot_name):
        """ Replaces the name for this bot """
        return _telegram_post(
            f'{self._api_base}/setMyName',
            data={
                'name': bot_name})

    def set_bot_description(self, descr):
        """ Replaces the description for this bot """
        return _telegram_post(
            f'{self._api_base}/setMyDescription',
            data={
                'description': descr})

    def set_commands(self, cmds):
        """ Replaces the commands available to users of this bot """
        self._known_commands, fmt_cmds = _validate_telegram_cmds(cmds)
        return _telegram_get(
            f'{self._api_base}/setMyCommands',
            data={
                'commands': fmt_cmds})

    def send_message(self, chat_id, text, disable_notifications=False):
        """ Send a text message to chat_id, or throw """
        msg = _telegram_post(f'{self._api_base}/sendMessage',
                             data={'chat_id': int(chat_id),
                                   'disable_notification': disable_notifications,
                                   'text': text})
        if 'message_id' not in msg:
            raise TelegramApiError(
                f'Failed to send message to chat {chat_id}: {msg}')

    def send_photo(self, chat_id, fpath, caption=None, disable_notifications=False):
        """ Send a picture to chat_id, or throw. fpath should be a path to a local file """
        msg = _telegram_post(
            f'{self._api_base}/sendPhoto',
            data={
                'chat_id': int(chat_id),
                'disable_notification': disable_notifications,
                'caption': str(caption) if caption is not None else ''},
            files={
                'photo': open(
                    fpath,
                    'rb')})
        if 'message_id' not in msg:
            raise TelegramApiError(
                f'Failed to send message to chat {chat_id}: {msg}')
        return True

    def poll_updates(self):
        """ Poll Telegram for events for this bot. Will call on_bot_received_message if this bot
        has a pending message, and it will ignore all other updates. """
        max_update_id = 0
        updates_prcd = 0
        for update in _telegram_get(
            f'{self._api_base}/getUpdates',
                params=self._updates_offset):
            try:
                max_update_id = max(
                    max_update_id, int(
                        update['update_id']) + 1)
            except BaseException:
                log.debug(
                    'Failed to parse Telegram update %s',
                    update,
                    exc_info=True)
                continue

            msg = _telegram_sanitize_user_message(update, self._known_commands)
            if msg is None:
                continue
            elif msg['cmd'] is not None:
                try:
                    cb = self._known_commands[msg['cmd']]
                    cb(self, msg)
                except BaseException:
                    # Swallow all errors: if processing fails, we should continue from the next one,
                    # failing here means we'd retry them forever
                    log.error(
                        'User error processing Telegram command %s',
                        msg['cmd'],
                        exc_info=True)
            else:
                self.on_bot_received_message(msg)

            updates_prcd += 1

        self._updates_offset = {'offset': max_update_id}
        return updates_prcd

    def on_bot_received_message(self, msg):
        """ Bot received a message. You should probably override this method. """
        print('Bot has msg ', msg)


class TelegramLongpollBot:
    """ Creates a Telegram bot that will poll for updates. On connect failure, will
    ignore and try to create a new bot next round (to work around rate limits) """

    def __init__(self, tok, poll_interval_secs, cmds=None, bot_name=None, bot_descr=None):
        """ See TelegramBot """
        self._t = None
        self._tok = tok

        self._commands = cmds
        self._bot_name = bot_name
        self._bot_descr = bot_descr

        self._scheduler = BackgroundScheduler()
        self._scheduler.start()
        self._poll_job = self._scheduler.add_job(
            func=self._poll_updates,
            trigger="interval",
            seconds=poll_interval_secs,
            next_run_time=datetime.datetime.now())

    def _poll_updates(self):
        self.connect()
        if self._t is None:
            return

        cnt = self._t.poll_updates()
        #log.debug('Telegram bot %s had %s updates',
        #          self._t.bot_info['first_name'], cnt)

    def connect(self):
        """ Requests bot to connect, if not connected yet """
        if self._t is not None:
            return

        try:
            self._t = TelegramBot(self._tok)
            if self._commands is not None:
                self._t.set_commands(self._commands)
            if self._bot_name is not None:
                self._t.set_bot_name(self._bot_name)
            if self._bot_descr is not None:
                self._t.set_bot_description(self._bot_descr)
            self.on_bot_connected(self._t)
        except TelegramRateLimitError:
            log.info('Telegram API rate limit, will try to connect later...')

    def send_photo(self, *a, **kw):
        self.connect()
        if self._t is None:
            log.error('Skipping request to send_photo, Telegram not connected')
            return
        self._t.send_photo(*a, **kw)

    def send_message(self, *a, **kw):
        self.connect()
        if self._t is None:
            log.error('Skipping request to send message, Telegram not connected')
            return
        self._t.send_message(*a, **kw)

    def on_bot_connected(self, bot):
        """ Callback when bot successfully connects to Telegram """
        log.info('Connected to Telegram bot %s', bot.bot_info['first_name'])
