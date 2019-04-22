
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
    constructor(api_base_url, webapp_base_url, templated_things_classes) {
        this.things = [];
        this.unknown_things= [];

        this.api_base_url = api_base_url;
        this.webapp_base_url = webapp_base_url;
        this.templated_things_classes = templated_things_classes;

        // Promise to be resolved when all objects have been initialized
        this.is_ready = $.Deferred();

        // Cache this for scope
        var self = this;

        // Init all templates
        this.tmpls_ready = [];
        for (var tmpl of templated_things_classes) {
            console.log("Init template ", tmpl.get_thing_path_name())
            self.tmpls_ready.push( tmpl.init_template(self.webapp_base_url) );
        }

        this.things_ready = $.Deferred();
        $.when(wget(this.api_base_url + "world/status")).then(function(things) {
            self.things = things;
            self.things_ready.resolve();
        });

        this.unknown_things_ready = $.Deferred();
        $.when(wget(this.api_base_url + "world/unknown_things")).then(function(things) {
            self.unknown_things = things;
            self.unknown_things_ready.resolve();
        });

        $.when(self.things_ready).then(function(){
            $.when(self.unknown_things_ready).then(function(){
                $.when.apply($, self.tmpls_ready).then(function() {
                    self.is_ready.resolve();
                });
            });
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

    get_thing_by_name(name) {
        for (var thing_name in this.things) {
            if (thing_name == name) return this.things[thing_name];
        }
        return null;
    }
}


