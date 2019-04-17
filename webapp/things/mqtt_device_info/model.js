
class MqttDeviceInfo extends TemplatedThing {
    /**
     * Check if a list of actions look like an interface for an MqttDevice
     */
    static matches_interface(actions) {
        return actions.includes("mqtt_status");
    }

    static get_thing_path_name() {
        return "mqtt_device_info";
    }

    constructor(things_server_url, name, supported_actions, status) {
        super("", name, [], status);
    }

    update_status(stat) {
        this.link_quality = stat.link_quality;
        this.battery_level = stat.battery_level;
    }
}

