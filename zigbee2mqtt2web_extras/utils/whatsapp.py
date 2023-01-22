import json
import requests
import base64

class WhatsApp:
    def __init__(self, cfg, test_mode):
        self._from_number = cfg['from_number']
        self._tok = cfg['tok']
        self._test_mode = test_mode

    def _url(self):
         return f'https://graph.facebook.com/v15.0/{self._from_number}/messages'

    def _headers(self):
        return {
          'Authorization': f'Bearer {self._tok}',
          'Content-Type': 'application/json',
        }

    def text(self, to_number, msg_text):
        if self._test_mode:
            print(f'WA Text {to_number}: {msg_text}')
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
        return requests.post(self._url(), headers=self._headers(), data=json.dumps(msg))

    def upload_image(self, fpath):
        if self._test_mode:
            print(f'WA upload image {fpath}')
            return 'DUMMY_WA_IMAGE_ID'
        url = f'https://graph.facebook.com/v15.0/{self._from_number}/media'
        headers = {
          'Authorization': f'Bearer {self._tok}',
        }
        msg = {
            "messaging_product": "whatsapp",
            "type": "image/jpeg",
        }
        files = {
            'file': ('n.jpg', open(fpath, 'rb'), 'image/jpeg', {'Expires': '0'}),
        }
        req = requests.post(url, headers=headers, data=msg, files=files)
        jreq = json.loads(req.text)
        return jreq['id']

    def send_image(self, to_number, image_id):
        if self._test_mode:
            print(f'WA Send image to {to_number}: {image_id}')
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
        return requests.post(self._url(), headers=self._headers(), data=json.dumps(msg))


    def message_from_template(self, to_number, template_name):
        if self._test_mode:
            print(f'WA Send template {template_name} to {to_number}')
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
        return requests.post(self._url(), headers=self._headers(), data=json.dumps(msg))

    def message_from_params_template(self, to_number, media_id):
        if self._test_mode:
            print(f'WA Send template media {to_number}, {media_id}')
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
        return requests.post(self._url(), headers=self._headers(), data=json.dumps(msg))
