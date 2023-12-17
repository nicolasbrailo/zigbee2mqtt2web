# zigbee2mqtt2web

zigbee2mqtt2web will expose a Zigbee network as a small set of REST endpoints, and provide a basic UI to manage your zigbee network with a web interface, with sensible defaults and minimal configuration. Clone, do `make run` and you're all set.


## What does it do?

The aim of the project is to read mqtt messages broadcasted by Zigbee2mqtt and translate them to objects with an API accessible through REST(ish) URLs, with a very limited set of dependencies, and very little configuration required. The goal is to enable developers to easily configure and extend a zigbee network using Python. It also includes an example web application that can show the objects registered in the network and perform actions on them. The project core is small and extensible so that new thing types may be supported; even non-MQTT based things, like media players with 3rd party API integrations. The project includes extensions for Sonos, Spotify and possibly other non-MQTT things I find useful.

The server is designed to be low footprint, so that it may run in a RaspberryPi. Even an RPI W Zero might work, though the lag in mqtt messages might get noticeable.


## Test run

Running this project should be trivial in any Linuxy (RaspberryPi) environment:

* Clone this repo
* Run `make install_system_deps` (to get a bunch of apt-get dependencies)
* Run `make install_dep_svcs` (to install zigbee2mqtt and mosquitto - optional if you already have these)
* Run `make install` - this will create a Python virtualenv for all the dependencies
* Run `make run`

You should now see a list of URLs being served. Going to $YOUR_HOST_IP:1234 in a browser should land you in a minimal UI that can be used to manage your Zigbee network. Note if your Zigbee2mqtt server is running in a different host, you'll need to edit zigbee2mqtt2web.conf.json to connect to the right server.


## Real run, extending

You'll probably want to run it in a less hacky way, and add your own custom behaviour (eg buttons won't work with the example server out of the box). You can try to:

* Extend main.py to include your custom behaviour. Here's a not-so-trivial example: https://github.com/nicolasbrailo/BatiCasa
* Use `make install_service` to install ZMW as a system service. Note you may want to change the service name in the template file, and you surely want to change the service port to 80 (and use authbind so you don't need to run as root) - but neither of these are required.
* Give your Zigbee2mqtt devices friendly names, so they are easier to identify in your UI. You can do this in your zigbee2mqtt.conf file.
* Change your UI: the default UI should work out of the box, but it's also simple to extend. It's built with React, and you can add your custom behaviour to app.js. Use `make ui` to rebuild and deploy your changes to css or js files.


## Why?
After trying out Hassio, Home-Assistant and OpenHAB I figured I didn't like them. I'm not too keen on installing an entire OS and fiddling with yaml files for days just to make a button play a video. What to do with all my Zigbee hardware and home automation ideas, then? Easy: spend a week hacking my own. This is the result; not nearly as pretty as Hassio but easier to setup. And now I can add my own buttons using plain Python and HTML.

Who should use this? If you:

* Have a few Zigbee devices but don't want to use a proprietary solution
* Prefer programming Python to debugging yaml files and reading manuals
* Don't mind some hacking

You may find this project useful.
