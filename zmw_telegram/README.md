# ZmwTelegram

MQTT to Telegram bot bridge for bidirectional messaging.

Runs a Telegram bot that receives commands and relays them over MQTT. Other services can register custom commands and send messages/photos through Telegram.

## MQTT

**Topic:** `mqtt_telegram`

**Methods (subscribe):**
- `register_command` - Register a Telegram command (`{cmd, descr}`)
- `send_photo` - Send photo to broadcast chat (`{path, msg?}`)
- `send_text` - Send text message (`{msg}`)

**Announces (publish):**
- `on_command/<cmd>` - Relayed Telegram command

## WWW

Provides a history of sent or received Telegram messages.

