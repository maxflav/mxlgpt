import json

config = None
class Config:
    config_dict = None

    def load_from_file(self):
        print("loading config from file")
        try:
            with open("config.json") as config_file:
                self.config_dict = json.load(config_file)
        except FileNotFoundError:
            print("Could not file config.json!")
            exit(0)
        except json.decoder.JSONDecodeError as e:
            print("Could not parse config.json")
            print(e)

    def get(self, *args):
        config_pointer = self.config_dict
        for a in args:
            if a not in config_pointer:
                return None
            config_pointer = config_pointer[a]
        return config_pointer


if config is None:
    config = Config()
    config.load_from_file()
