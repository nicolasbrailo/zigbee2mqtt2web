"""
Whatsapp wrapper, to upload files and send messages. Probably not compliant with the terms of service, and may
break at any time.

A lot of setup is required, and any of these steps may break at any time:

* Create a developer account at developers.facebook.com
* Create new business app at https://developers.facebook.com/apps/
* In the app dashboard, add Whatsapp integration
* In the Whatsapp integration there should be steps to get a temporary token and to test with curl. This includes enrolling the target phone numbers.
* Get the origin phone number from the dashboard, to be used as the source phone number for this app (or add your own number; this is probably safer)
* In the WhatsApp integration page, look for "Permanent token" (under configuration?)
    - https://developers.facebook.com/docs/whatsapp/business-management-api/get-started#1--acquire-an-access-token-using-a-system-user-or-facebook-login
    - https://stackoverflow.com/questions/72685327/how-to-get-permanent-token-for-using-whatsapp-cloud-api
  The permanent token is, basically, a password for your Facebook account
* Use the origin phone number and the permanent token to configure this object

Note you can't send arbitrary messages to a phone number, you will need to
1. Send a template message
2. Get the target number to interact via WhatsApp (this will let you send arbitrary messages only for a set period of time)
"""
import json
import requests
import base64

import logging
logger = logging.getLogger(__name__)

# Comment out to see requests to WA's API
logging.getLogger('urllib3.connectionpool').setLevel(logging.INFO)

class WhatsApp:
    """ WA integration, may be against WA ToS """

    def __init__(self, cfg, test_mode=True):
        self._test_mode = test_mode
        self._targets = cfg['notify_targets']

        self._msg_url = f'https://graph.facebook.com/v15.0/{cfg["from_number"]}/messages'
        self._media_url = f'https://graph.facebook.com/v15.0/{cfg["from_number"]}/media'

        self._headers = {
            'Authorization': f'Bearer {cfg["tok"]}',
        }

        self._json_headers = {
            'Authorization': f'Bearer {cfg["tok"]}',
            'Content-Type': 'application/json',
        }

    def upload_image(self, fpath):
        """ Upload image to WA server, returns media ID to use when sending a message """
        logger.info('WA uploaded image %s', fpath)
        if self._test_mode:
            return 'DUMMY_WA_IMAGE_ID'
        msg = {
            "messaging_product": "whatsapp",
            "type": "image/jpeg",
        }
        files = {'file': ('n.jpg', open(fpath, 'rb'),
                          'image/jpeg', {'Expires': '0'}), }
        req = requests.post(
            self._media_url,
            headers=self._headers,
            data=msg,
            files=files)
        jreq = json.loads(req.text)
        return jreq['id']

    def text(self, msg_text):
        """ Send text. This won't work unless the target has interacted with the origin number in the last N hours """

        def _text(to_number, msg_text):
            logger.info('WA Text %s: %s', to_number, msg_text)
            if self._test_mode:
                return
            msg = {
                "to": to_number,
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "type": "text",
                "text": {
                    "preview_url": False,
                    "body": msg_text,
                }
            }
            return requests.post(
                self._msg_url,
                headers=self._json_headers,
                data=json.dumps(msg))

        return [_text(num, msg_text) for num in self._targets]

    def send_image(self, image_id):
        """ Send image to_number. Same restrictions as text() apply """

        def _send_image(to_number, image_id):
            logger.info('WA send image to %s, id %s', to_number, image_id)
            if self._test_mode:
                return
            msg = {
                "to": to_number,
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "type": "image",
                "image": {
                    "id": image_id,
                    "caption": "your-image-caption"
                }
            }
            return requests.post(
                self._msg_url,
                headers=self._json_headers,
                data=json.dumps(msg))
        return [_send_image(num, image_id) for num in self._targets]

    def message_from_template(self, template_name):
        """ Send template to_number. This works even if the target hasn't interacted first, but target must be
        enrolled in the test program || the origin should be a proper business account. """

        def _message_from_template(to_number, template_name):
            logger.info('WA send template %s to %s', template_name, to_number)
            if self._test_mode:
                return
            msg = {
                "to": to_number,
                "type": "template",
                "messaging_product": "whatsapp",
                "template": {
                    "name": template_name,
                    "language": {
                        "policy": "deterministic",
                        "code": "en_us"
                    },
                },
            }
            return requests.post(
                self._msg_url,
                headers=self._json_headers,
                data=json.dumps(msg))
        return [_message_from_template(num, template_name)
                for num in self._targets]

    def message_from_params_template(self, media_id):
        """ Send a templated messages, with a text and media params. Same restrictions as
        message_from_template apply. The template name must be configured in the dashboard, eg
        https://business.facebook.com/wa/manage/message-templates/
        """

        def _message_from_params_template(to_number, media_id):
            logger.info(
                'WA send template with media %s to %s',
                media_id,
                to_number)
            if self._test_mode:
                return
            msg = {
                "to": to_number,
                "type": "template",
                "recipient_type": "individual",
                "messaging_product": "whatsapp",
                "template": {
                    "name": "sample_purchase_feedback",
                    "language": {
                        "policy": "deterministic",
                        "code": "en_us"
                    },
                    "components": [
                        {
                            "type": "header",
                            "parameters": [
                                {
                                    "type": "image",
                                    "image": {
                                        "id": media_id
                                    }
                                }
                            ]
                        },
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": "HOLA!"},
                            ]
                        }
                    ],
                }
            }
            return requests.post(
                self._msg_url,
                headers=self._json_headers,
                data=json.dumps(msg))
        return [_message_from_params_template(
            num, media_id) for num in self._targets]
