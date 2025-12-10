# mqtt_whatsapp

MQTT to WhatsApp bridge for sending messages.

## Behaviour

Sends photos and messages to WhatsApp. Maintains a message history. Text messages are not yet implemented, because the API is quite complicated.

## MQTT

**Topic:** `mqtt_whatsapp`

**Methods (subscribe):**
- `send_photo` - Send photo (`{path, msg}`)
- `send_text` - Send text message (`{msg}`) - not implemented

## WWW Endpoints

- `/messages` - Message history JSON
