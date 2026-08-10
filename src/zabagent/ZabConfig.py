import jsonpickle


class Generator:

    def __init__(self, idx=1):
        self.name = f"TEST"
        self.system_id = idx

        self.buffers = ["buffer_le", "buffer_le_3"]


class Config:

    def __init__(self, tgs=2):
        self.location = ""
        self.zabbix = "zabbix.logicelements.cz"
        self.zabbix_port = 10051

        self.mysql = "localhost"
        self.database = "BVMS"
        self.user = "VMS"
        self.password = "Vms2015"

        self.info = "info_le"

        self.tgs = [Generator(i+10) for i in range(tgs)]

    @staticmethod
    def load(filename):

        # Open and read file
        try:
            f = open(filename, 'r', encoding='utf-8')
        except FileNotFoundError:
            return []
        js = f.read()
        # Decode array of objects
        data = jsonpickle.decode(js)
        f.close()

        return data

    def store(self, filename):
        f = open(filename, 'w', encoding='utf-8')
        jsonpickle.set_preferred_backend('json')
        js = jsonpickle.encode(self, indent=2)
        f.write(js)
        f.close()


if __name__ == '__main__':
    cfg = Config(2)

    cfg.store("config.json")

    cfg2 = Config.load("config.json")

    print(cfg)
    print(cfg2)
