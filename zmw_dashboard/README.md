# ZmwDashboard

Dashboard system that ties all other ZMW services to a mobile friendly interface.

![](README_screenshot.png)

This service integrates with all other ZMW services running in the system to

* Enable quick lights control.
* Exposes scenes ("fake" buttons created by a user-service, which perform a set of actions on other ZmwServices).
* Exposes a list of sensors, by default showing temperature.
* Speaker-announce: send an announcement through the Sonos LAN speakers in your network (user recording not supported here: running the dashboard via HTTPS with a self-signed cert is painful!)
* Each section (lights, scenes, sensors, cameras...) can link to the main service, which exposes further functionality.
* Contact monitoring: expose door states, and lets you bypass chimes (if your door is configured to play a chime when open).
* Heating: monitor heating state and turn it on/off
* Doorbell cam: show last snap of the doorbell camera, and lets you take a new one. Also displays if the doorbell has rung recently.
* Theming: supports Classless CSS themes.
* Links to user-defined services: add more links to all of those services running in your LAN, so you have a centralised place to access them.
* System alerts: display any system level alerts, such as services down or your cat running out of food.

