# ZmwLighs

Zigbee light discovery and control service.

![](README_screenshot.png)

Connects to Zigbee2MQTT, discovers all light devices on the network, and exposes them via a web API. Applies light helper patches for extended functionality. The app favours convention over configuration, and will

* Automatically group set of lights; if a set of lights starts with a prefix, they will be presented as a group. A set of lights like "TVRoomLight1", "TVRoomLight2", "TVRoomLight2", for example, will be shown as "Light1", "Light2", "Light3", under group "TVRoom".
* Show a compact, mobile friendly, view of all the lights discovered, and quickly adjust brightness and on/off status.
* An extended configuration panel is shown for lights that support extra settings. Currently supported: RGB, colour temperature, light effects.
* Backend service contains random patches to work around/normalize behaviour of a few different lights, eg adding support for RGB methods where only CIE XY is supported. Don't try to pick black colour for your lights.
* Backend provides a hash for the known lights. This lets the frontend query copious amount of metadata per light, and cache it, without risk of showing a stale network to the user.
* Switches support: because switches behave very closely to lights, this service will also offer an endpoint to query switches.
* User-defined actions: users may specify a set of actions when creating the react component. By providing a map of {label => url}, the lights service will render this in its matching group. This can be used to set up scenes, or any other quick action.

## WWW Endpoints

- `/get_lights` - Returns JSON array of all discovered lights with their state.
- `/z2m/*` - Z2M web service endpoints (device listing, control).
- `/z2m/get_known_things_hash` - Returns a hash of the known devices, so the UI can check if the network has changed without loading all of the metadata.
- `/z2m/ls' - returns a small list of all known lights names.
- `/z2m/get_world` - returns state of all the lights registered in this service.
- `/z2m/meta/<thing_name>` - retrieves a list of device capabilities. This method will return a lot of data!
- `/z2m/set/<thing_name>` - set properties of a devicer. For example, call with `{brightness: 50}`
- `/z2m/get/<thing_name>` - retrieves properties of a device

