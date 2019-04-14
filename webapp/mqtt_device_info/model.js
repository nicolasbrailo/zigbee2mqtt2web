
class MqttDeviceInfo extends TemplatedThing {
    constructor(things_server_url, name, supported_actions, status) {
        super("", name, [], status);
    }

    update_status(stat) {
        this.link_quality = stat.link_quality;
        this.battery_level = stat.battery_level;
    }
}

