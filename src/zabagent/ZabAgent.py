import os
import sys

import win32serviceutil
import win32service
import servicemanager

from time import sleep
from datetime import *

from pyvms.DbMySql import DbMysql
from . import ZabConfig as Cfg
from . import ZabSender as Snd


class ZabAgent:

    CFG_DEFAULT = os.path.join(os.path.dirname(__file__), "data", "config_default.json")

    def __init__(self):
        self._running = False
        self.db = DbMysql()
        self.cfg = Cfg.Config(tgs=1)
        self.cfg.store(self.CFG_DEFAULT)
        self.snd = None

    def stop(self):
        self._running = False
        self.db.close()

    def start(self):
        self._running = True
        self.cfg = Cfg.Config.load(self.CFG_DEFAULT)
        self.db.connect(
            host=self.cfg.mysql,
            database=self.cfg.database,
            user=self.cfg.user,
            password=self.cfg.password
        )
        self.snd = Snd.ZabSender(self.cfg.zabbix, self.cfg.zabbix_port)

    def main(self):
        while self._running:
            details = self.db.get_table_details(self.cfg.database)
            for tg in self.cfg.tgs:
                now = datetime.now()

                inf = self.db.get_info(self.cfg.info, tg.system_id)

                items = Snd.ZabItems()

                items.speed = round(1e8 / inf[4]*60, 4)
                items.timestamp_age = int((now - inf[5]).total_seconds())
                items.config_age = int((now - inf[6]).total_seconds())
                items.info_age = int((now - inf[3]).total_seconds())

                el = next((x for x in details if x[0] == tg.buffers[0]), [0, 0, now])
                items.buf_age_1 = int((now - el[2]).total_seconds())
                items.buf_rows_1 = el[1]
                items.buf_bulk_1 = inf[12]

                el = next((x for x in details if x[0] == tg.buffers[1]), [0, 0, now])
                items.buf_age_2 = int((now - el[2]).total_seconds())
                items.buf_rows_2 = el[1]
                items.buf_bulk_2 = inf[13]

                print(items)
                self.snd.send(items)

            sleep(5)


class ZabAgentFrame(win32serviceutil.ServiceFramework):
    _svc_name_ = "ZabAgent"
    _svc_display_name_ = "VMS zabbix agent"
    _svc_description_ = "VMS - Zabbix agent sends metrics on VMS software to Zabbix"

    def __init__(self,args):
        win32serviceutil.ServiceFramework.__init__(self,args)
        self._impl = ZabAgent()

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self._impl.stop()
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STOPPED,
                              (self._svc_name_, ''))
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self._impl.start()
        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        self._impl.main()


if __name__ == '__main__':
    if len(sys.argv) == 1:
        _impl = ZabAgent()
        _impl.start()
        _impl.main()
    else:
        win32serviceutil.HandleCommandLine(ZabAgentFrame)
