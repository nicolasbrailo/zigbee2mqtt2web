
class TemplatedThing {
    /**
     * Fetches view and style resources for its subclass
     */
    static init_template() {
        var subclass = this;

        if (! subclass.get_thing_type ) {
            console.error("Subclass must define static get_thing_type()");
        }

        // Add css to document
        var fileref = document.createElement("link");
        fileref.rel = "stylesheet";
        fileref.type = "text/css";
        fileref.href = "things/"+ subclass.get_thing_type() + "/style.css";
        document.getElementsByTagName("head")[0].appendChild(fileref)

        subclass.template_ready = $.Deferred();

        var view_url = "things/"+ subclass.get_thing_type() + "/view.html";
        $.ajax({
            url: view_url,
            cache: false,
            type: 'get',
            dataType: 'html',
            success: function(tmpl) {
                if (!Handlebars || !Handlebars.registerHelper) {
                    console.error("Handlebars plugin not found");
                }

                subclass.render_template = Handlebars.compile(tmpl);
                subclass.template_ready.resolve(); 
                if (subclass.on_template_ready) {
                    subclass.on_template_ready();
                }
            }
        });
    }

    constructor(things_server_url, name, supported_actions, status) {
        var klass = Object.getPrototypeOf(this).constructor;
        if (klass.template_ready.state() != 'resolved') {
            console.error("Template system not initialized");
        }

        if (! this.update_status) {
            console.error("Subclass must define update_status()");
        }

        this.action_base_url = things_server_url + 'things/' + name;
        this.name = name;
        // HTML ids can't contain whitespaces
        this.html_id = name.split(' ').join('_');
        this.supported_actions = supported_actions;
        this.update_status(status);

        console.log("Created thing ", this);
    }

    request_action(action_url) {
        var url = this.action_base_url + action_url
        var self = this;
        $.when(wget(url)).then(function(thing_status) {
            self.update_status(thing_status);
        });
    }

    create_ui() {
        var klass = Object.getPrototypeOf(this).constructor;
        return klass.render_template(this);
    }

    // update_status(new_status)
    // static get_thing_type()
}

