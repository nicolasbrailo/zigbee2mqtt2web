# zigbee2mqtt2flask
## What does it do?
The aim of the project is to read mqtt messages broadcasted by Zigbee2mqtt and translate them to objects with an API accessible through REST(ish) URLs. It also includes an example web application that can show the objects registered in the network and perform actions on them.

The project is extensible so that new thing types may be supported, though only the devices I have in my own network have been tested.

The server is designed to be low footprint, so that it may run in a RaspberryPi. Even an RPI W Zero might work, though the lag in mqtt messages might get noticeable. This also means a lot of processing is done on the client side, though even a crappy old phone seems to be capable of running the example web-app just fine.

## What does it NOT do?
Autodiscovery of any kind: this project is not meant to be an off-the-shelf home automation solution but a library that can help translating zigbee/mqtt to a web app.

All the setup and all automation is user defined. If you need a device to be visible you'll need to register it using a Python script. It's also recommended that you give your devices friendly names in Zigbee2mqtt's configuration, otherwise you'll be needing ugly IDs for the REST endpoints too. See the INSTALL guide for details.

## Why?
After trying out Hassio, Home-Assistant and OpenHAB I figured I didn't like them. I'm not too keen on installing an entire OS and fiddling with yaml files for days (especially with Hassio) just to make a button play a video. What to do with all my Zigbee hardware and home automation ideas, then? Easy: spend a week hacking my own. This is the result; not nearly as pretty as Hassio but easier to setup. And now I can add my own buttons using plain Python and HTML.

## Who should use this?
If you:

* Have a few Zigbee devices but don't want to use a proprietary solution
* Prefer programming Python to debugging yaml files and reading manuals
* Don't mind some hacking

Then you may find this project useful. If you expect a project that works out of the box, you'll probably be disappointed.

