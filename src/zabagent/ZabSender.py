import logging

from zabbix_utils import ItemValue, Sender


class ZabItems:
    """
    Class containing all items for one Turbo generator
    """
    def __init__(self):
        self.name = 'TEST'
        self.speed = 0.0
        self.info_age = 0
        self.timestamp_age = 0
        self.config_age = 0
        self.buf_rows_1 = 0
        self.buf_rows_2 = 0
        self.buf_age_1 = 0
        self.buf_age_2 = 0
        self.buf_bulk_1 = 0
        self.buf_bulk_2 = 0

    def __repr__(self):
        props = [x for x in vars(self) if not x.startswith("_")]
        ret = "ZabItem: "
        for p in props:
            # if getattr(self, p) != 0:
            ret += f"{p}={getattr(self, p)}, "
        return ret[:-2]


class ZabSender:

    def __init__(self, server, port, log=False):
        self.sender = Sender(server=server, port=port)

        if log:
            logging.basicConfig(
                format=u'[%(asctime)s] %(levelname)s %(message)s',
                level=logging.DEBUG
            )

    def send(self, data):
        items = [
            ItemValue(data.name, 'vms.speed', str(data.speed)),
            ItemValue(data.name, 'vms.info_age', str(data.info_age)),
            ItemValue(data.name, 'vms.timestamp_age', str(data.timestamp_age)),
            ItemValue(data.name, 'vms.config_age', str(data.config_age)),
            ItemValue(data.name, 'vms.buf_rows_1', str(data.buf_rows_1)),
            ItemValue(data.name, 'vms.buf_rows_2', str(data.buf_rows_2)),
            ItemValue(data.name, 'vms.buf_age_1', str(data.buf_age_1)),
            ItemValue(data.name, 'vms.buf_age_2', str(data.buf_age_2)),
            ItemValue(data.name, 'vms.buf_bulk_1', str(data.buf_bulk_1)),
            ItemValue(data.name, 'vms.buf_bulk_2', str(data.buf_bulk_2))
        ]

        response = self.sender.send(items)
        processed = response[next(iter(response))].processed
        if len(items) != processed:
            print("Something wrong with zabbix trapper")
            print(response)


if __name__ == '__main__':
    sender = ZabSender("zabbix.logicelements.cz", 10051)
    item = ZabItems()

    item.speed = 125.0
    item.info_age = 1
    item.timestamp_age = 2
    item.config_age = 3
    item.buf_rows_1 = 4
    item.buf_rows_2 = 5
    item.buf_age_1 = 6
    item.buf_age_2 = 7
    item.buf_bulk_1 = 8
    item.buf_bulk_2 = 9

    sender.send(item)
