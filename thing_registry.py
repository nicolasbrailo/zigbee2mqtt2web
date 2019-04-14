import json

class ThingRegistry(object):
    """
    Acts as a dictionary of all known things and also as a bridge between
    mqtt and local model objects: the registry knows the id of each thing,
    so it can map an mqtt message to the object which should receive it
    """

    def __init__(self):
        self.known_things = {}
        self.name_to_id = {}
        self.unknown_things = set()

    def register_thing(self, obj):
        if obj.get_pretty_name() in self.name_to_id.keys():
            raise KeyError('Thing {} ({}) already registered'.format(obj.get_pretty_name(), obj.get_id()))

        self.known_things[obj.get_id()] = obj
        self.name_to_id[obj.get_pretty_name()] = obj.get_id()

    def get_by_name_or_id(self, name_or_id):
        if name_or_id in self.name_to_id.keys():
            id = self.name_to_id[name_or_id]
            return self.known_things[id]

        # If it's not a name it must be an id. Else fail
        return self.known_things[name_or_id]

    def get_known_things_names(self):
        return list(self.name_to_id.keys())

    def get_unknown_ids(self):
        return list(self.unknown_things)

    def on_thing_message(self, thing_id, topic, json_msg):
        if thing_id in self.known_things.keys():
            if not self.known_things[thing_id].consume_message(topic, json_msg):
                self.on_unknown_message(topic, json.dumps(json_msg))
        else:
            if thing_id not in self.unknown_things:
                self.unknown_things.add(thing_id)
                print('Thing {} added to registry of unknown things'.format(thing_id))

    def on_unknown_message(self, topic, payload):
        print('Received message that can\'t be understood:' +\
                    '\t{}\n\t{}'.format(topic, payload))

