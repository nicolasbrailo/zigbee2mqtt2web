
class Lamp extends TemplatedThing {
    static get_thing_type() {
        return "lamp";
    }

    constructor(things_server_url, name, supported_actions, status) {
        super(things_server_url, name, supported_actions, status);

        this.supports_onoff = supported_actions.includes('turn_on') &&
                                supported_actions.includes('turn_off');
        this.supports_brightness = supported_actions.includes('set_brightness');
        this.has_color = supported_actions.includes('set_rgb');

        // Register object UI callbacks
        var self = this;

        $(document).on('click', '#lamp_open_panel_ctrl'+this.html_id,
            function(){ $('#lamp_detailed_panel_ctrl'+self.html_id).toggle(); });

        $(document).on('click', '#lamp_is_on_checkbox'+this.html_id,
            function(){ self.update_on_state_from_ui(); });

        $(document).on('click', '#lamp_set_brightness_slider'+this.html_id,
            function(){ self.update_brigthness_from_ui(); });
        $(document).on('touchend', '#lamp_set_brightness_slider'+this.html_id,
            function(){ self.update_brigthness_from_ui(); });

        $(document).on('change', '#lamp_set_rgb'+this.html_id,
            function(){ self.update_color_from_ui();});
        /* TODO: Could be interesting with a debounce
        $(document).on('input', '#lamp_set_rgb'+this.html_id,
            function(){  self.update_color_from_ui(); });
        */
    }

    update_status(stat) {
        this.is_on = stat.is_on;
        this.brightness = stat.brightness;
    }

    update_on_state_from_ui() {
        var should_be_on = $('#lamp_is_on_checkbox'+this.html_id).is(':checked');
        this.request_action((should_be_on? '/turn_on' : '/turn_off'));
    }

    update_brigthness_from_ui() {
        var brightness_pct = $('#lamp_set_brightness_slider'+this.html_id).val();
        this.request_action('/set_brightness/' + brightness_pct);
    }

    update_color_from_ui() {
        var color = $('#lamp_set_rgb'+this.html_id).val();
        this.request_action('/set_rgb/' + color.substring(1));
    }
}

