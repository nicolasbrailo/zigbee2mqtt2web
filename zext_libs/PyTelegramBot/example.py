from pytelegrambot import TelegramLongpollBot


class TelBotExample(TelegramLongpollBot):
    def __init__(self, tok, poll_interval_secs):
        cmds = [
            ('hi', 'Usage: /hi [msg]', self._hi),
            ('click', 'Usage: /click', self._click),
        ]
        super().__init__(
            tok,
            poll_interval_secs=poll_interval_secs,
            bot_name='ExampleBot',
            bot_descr='Example Telegram Bot',
            cmds=cmds)

    def on_bot_connected(self, bot):
        log.info('Connected to Telegram bot %s', bot.bot_info['first_name'])

    def on_bot_received_message(self, msg):
        log.info('Telegram bot received a message: %s', msg)

    def _hi(self, bot, msg):
        if len(msg['cmd_args']) == 0:
            self.send_message(msg['from']['id'], "HOLA")
        else:
            t = ' '.join(msg['cmd_args'])
            self.send_message(msg['from']['id'], f"Echo: {t}")

    def _click(self, bot, msg):
        self.send_photo(msg['from']['id'], "/home/foo/bar.jpg",
                        caption="Pretty snap", disable_notifications=True)
