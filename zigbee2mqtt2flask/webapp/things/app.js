
var wget = function(url) {
    var d = $.Deferred();
    $.ajax({
      type: 'GET',
      dataType: 'json',
      url: url,
      success: function(msg){ d.resolve(msg); },
      error: function(request, server_status, error){ d.resolve(null); },
    });
    return d;
}


class ThingsApp {
    static init_all_templates(webapp_base_url) {
        Lamp.init_template(webapp_base_url);
        MediaPlayer.init_template(webapp_base_url);
        MqttDeviceInfo.init_template(webapp_base_url);

        var all_done = $.Deferred();
        $.when(Lamp.template_ready).then(function() {
            $.when(MediaPlayer.template_ready).then(function() {
                $.when(MqttDeviceInfo.template_ready).then(function() {
                    all_done.resolve();
                });
            });
        });

        return all_done;
    }

    constructor(api_base_url) {
        this.api_base_url = api_base_url;
        this.things = [];
        this.unknown_things= [];

        this.is_ready = $.Deferred();
        this.things_ready = $.Deferred();
        this.unknown_things_ready = $.Deferred();

        var self = this;

        $.when(self.things_ready).then(function(){
            $.when(self.unknown_things_ready).then(function(){
                self.is_ready.resolve();
            });
        });

        $.when(wget(this.api_base_url + "world/status")).then(function(things) {
            self.things = things;
            self.things_ready.resolve();
        });

        $.when(wget(this.api_base_url + "world/unknown_things")).then(function(things) {
            self.unknown_things = things;
            self.unknown_things_ready.resolve();
        });
    };

    get_things_of_type(thing_class) {
        if (!thing_class) return this.things;

        var matching_things = [];
        for (var thing_name in this.things) {
            var thing = this.things[thing_name];
            var is_a_duck = thing_class.matches_interface(thing.supported_actions); 
            if (is_a_duck) {
                var mapped_thing = new thing_class(this.api_base_url, thing_name,
                                             this.things[thing_name].supported_actions,
                                             this.things[thing_name].status)
                matching_things.push(mapped_thing);
            }
        }

        return matching_things;
    }
}


