
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
    constructor(base_url) {
        this.base_url = base_url;
        this.things = [];
        this.unknown_things= [];

        this.ready = $.Deferred();
        this.things_ready = $.Deferred();
        this.unknown_things_ready = $.Deferred();

        var self = this;

        $.when(self.things_ready).then(function(){
            $.when(self.unknown_things_ready).then(function(){
                self.ready.resolve();
            });
        });

        $.when(wget(this.base_url + "things/get_world_status")).then(function(things) {
            self.things = things;
            self.things_ready.resolve();
        });

        $.when(wget(this.base_url + "things/unknown_things")).then(function(things) {
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
                var mapped_thing = new thing_class(this.base_url, thing_name,
                                             this.things[thing_name].supported_actions,
                                             this.things[thing_name].status)
                matching_things.push(mapped_thing);
            }
        }

        return matching_things;
    }
}


