
class MediaPlayer extends TemplatedThing {
    static get_thing_type() {
        return "media_player";
    }

    static on_template_ready(tmpl) {
        Handlebars.registerHelper('media_player_formatSeconds', function(seconds, options) {
            // Map seconds to HH:MM:SS
            return (new Date(seconds * 1000).toISOString()).substr(11, 8);
        });
    }

    constructor(things_server_url, name, supported_actions, status) {
        super(things_server_url, name, supported_actions, status);

        // Register object UI callbacks
        var self = this;
        // Div ID: '#media_player_'+this.html_id+'_ctrl'
        $(document).on('click',    '#media_player_'+this.html_id+'_play',     function(){ self.on_play(); });
        $(document).on('click',    '#media_player_'+this.html_id+'_stop',     function(){ self.on_stop(); });
        $(document).on('click',    '#media_player_'+this.html_id+'_mute',     function(){ self.on_mute(); }); 
        $(document).on('click',    '#media_player_'+this.html_id+'_prev',     function(){ self.on_prev(); });
        $(document).on('click',    '#media_player_'+this.html_id+'_next',     function(){ self.on_next(); });
        $(document).on('click',    '#media_player_'+this.html_id+'_volume',   function(){ self.on_volume(); });
        $(document).on('touchend', '#media_player_'+this.html_id+'_volume',   function(){ self.on_volume(); });
        $(document).on('click',    '#media_player_'+this.html_id+'_playtime', function(){ self.on_playtime(); });
        $(document).on('touchend', '#media_player_'+this.html_id+'_playtime', function(){ self.on_playtime(); });
    }

    update_status(new_status) {
        // Build minimal required defaults
        if (!new_status.name) {
            console.error("Unusable media player state: ", new_status);
            throw new Error("Unusable media player state");
        }

        new_status.media = new_status.media || {};
        new_status.media.player_state = new_status.media.player_state || "Unknown state";
        // Adjust duration and current_time
        new_status.media.duration = Math.floor(new_status.media.duration || 0);
        new_status.media.current_time = Math.floor(new_status.media.current_time || new_status.media.duration);
        // Adjust volume scale
        new_status.media.volume_level = (new_status.media.volume_level || 0) * 100;

        // Pick an icon from all available, or use default icon if none is present
        {
            if (new_status.media.icon) {
                // Backend service provided icon, use that one
            } else if (new_status.media.media_metadata && new_status.media.media_metadata.images) {
                // Icons available from media, pick first non-null (if any)
                $.each(new_status.media.media_metadata.images, function(_, icon) {
                    if (icon) {
                        new_status.media.icon = icon.url;
                        return false;
                    }
                });
            }
            
            if (!new_status.media.icon) {
                // No icon found. Use default
                new_status.media.icon = 'things/media_player/icons/chromecast.png'
            }
        }

        // TODO: Trigger UI update
        this.status = new_status;
    }

    on_play()     { this.request_action('/play'); }
    on_stop()     { this.request_action('/stop'); }
    on_mute()     { this.request_action('/mute'); } 
    on_prev()     { this.request_action('/prev'); }
    on_next()     { this.request_action('/next'); }
    on_volume()   { this.request_action( '/set_volume/' + $('#media_player_'+this.html_id+'_volume').val()); }
    on_playtime() { }//this._request_action('/play'); }
}

