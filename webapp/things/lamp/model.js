
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
            function(){ self.update_color_from_ui(); });
        $(document).on('input', '#lamp_set_rgb'+this.html_id,
            function(){ self.throttled_update_color_from_ui(); });
    }

    updateUI() {
        var show_panel = $('#lamp_detailed_panel_ctrl'+this.html_id).is(':visible');
        $('#lamp_view'+this.html_id).replaceWith(this.create_ui());
        if (show_panel) $('#lamp_detailed_panel_ctrl'+this.html_id).show();
    }

    update_status(stat) {
        this.is_on = stat.is_on;
        this.brightness = stat.brightness;
        this.rgb_color = stat.rgb;
    }

    update_on_state_from_ui() {
        var should_be_on = $('#lamp_is_on_checkbox'+this.html_id).is(':checked');
        this.is_on = should_be_on;
        this.updateUI();
        this.request_action((should_be_on? '/turn_on' : '/turn_off'));
    }

    update_brigthness_from_ui() {
        var brightness_pct = $('#lamp_set_brightness_slider'+this.html_id).val();
        this.brightness = brightness_pct;
        this.updateUI();
        this.request_action('/set_brightness/' + brightness_pct);
    }

    update_color_from_ui() {
        var color = $('#lamp_set_rgb'+this.html_id).val().substring(1);
        this.rgb_color = color;
        this.updateUI();
        this.request_action('/set_rgb/' + color);
    }

    throttled_update_color_from_ui() {
        if (this.timeout_active) return;

        var throttle_time = 250;
        var self = this;
        this.timeout_active = setTimeout(function(){
                clearTimeout(self.timeout_active);
                self.timeout_active = null; 
            }, throttle_time);

        var color = $('#lamp_set_rgb'+this.html_id).val().substring(1);
        this.request_action('/set_rgb/' + color);
    }
}

