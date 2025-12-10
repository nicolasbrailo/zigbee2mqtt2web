# baticasa_doorbell

Doorbell event handler and notification coordinator.

Orchestrates door events:
* plays announcement sounds on doorbell button press
* sends photos via WhatsApp/Telegram when cam detects motion
* responds to Telegram commands (`/door_snap`) if user requests door picture
* Manages door-open scene based on contact sensor and geolocation (automatically turn on lights if it's dark out when the door opens)

