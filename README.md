# zigbee2mqtt2web

zigbee2mqtt2web will expose a Zigbee network as a small set of REST endpoints, and provide a basic UI to manage your zigbee network with a web interface, with sensible defaults and minimal configuration. Clone, do `install_all_svcs.sh` and configure your network. Some things may work.


## What does it do?

The aim of the project is to read mqtt messages broadcasted by Zigbee2mqtt and translate them to objects with an API accessible through REST(ish) URLs, with a very limited set of dependencies, and very little configuration required. The goal is to enable developers to easily configure and extend a zigbee network using Python. The project core is small and extensible so that new thing types may be supported; even non-MQTT based things, like media players with 3rd party API integrations. The project includes extensions for Sonos, Spotify and possibly other non-MQTT things I find useful.

The server is designed to be low footprint, so that it may run in a RaspberryPi. Some time ago even an RPI W Zero might have worked, but now this project runs multiple services and a Zero is unlikely to be a good target anymore.

## Why?
A long time ago - almost 10 years ago? - after trying out Hassio, Home-Assistant and OpenHAB I figured I didn't like them. I'm not too keen on installing an entire OS and fiddling with yaml files for days just to make a button play a video. What to do with all my Zigbee hardware and home automation ideas, then? Easy: spend a week hacking my own. This is the result; not nearly as pretty as Hassio but easier to setup (or that was the case in 2017ish). And now I can add my own buttons using plain Python and HTML.

Who should use this? If you:

* Have a few Zigbee devices but don't want to use a proprietary solution
* Prefer programming Python to debugging yaml files and reading manuals
* Don't mind some hacking

You may find this project useful.

## Architecture and Creating a new service

ZMW is pretty simple:

* zzmw_lib/www has all of the web helpers, including css and base app js helpers. An app needs to be started by its html.
* zzmw_lib/zzmw_lib/*mqtt* has different ZMW service base classes. Pick one for your new service.
* zzmw_lib/zzmw_lib/service_runner is what launches the service. It will start a flask server and your app in parallel, and handle things like journal logs and basic www styles
* zz2m is the proxy to zigbee2mqtt

Start a new service by copying an existing one. Then:

* The main app entry point should be the same name as your service directory. For example, if the service directory is called "zmw_foo", the main entry point for systemd will be "zmw_foo/zmw_foo.py". If your names don't match, the app will work but install and monitoring scripts will break.
* Build your impl in your py file, update the www entry point in www/index.html and www/app.js
* Update any deps in your rebuild_deps makefile target
* Build with `make rebuild_deps`, then `make rebuild_ui`
* Try it out with `make devrun`
* When ready, `make install_svc`. The service will now forever run in the background and you can monitor it from servicemon.

