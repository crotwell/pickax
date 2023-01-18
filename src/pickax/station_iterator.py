from abc import ABC, abstractmethod
from obspy.clients.fdsn import Client


class StationIterator(ABC):
    def __init__(self):
        self.__empty__ = None, None
    @abstractmethod
    def next(self):
        return self.__empty__
    @abstractmethod
    def prev(self):
        return self.__empty__
    def beginning(self):
        pass
    def ending(self):
        pass

class FDSNStationIterator(StationIterator):
    def __init__(self, query_params, dc_name="IRIS", debug=False):
        self.debug = debug
        self.__empty__ = None, None
        self.dc_name = dc_name
        self.query_params = dict(query_params)
        if "level" not in query_params:
            self.query_params["level"] = "channel"
        self.net_idx = 0
        self.sta_idx = -1
        self.inv = self.__load__()

    def __load__(self):
        client = Client(self.dc_name, debug=self.debug)
        return client.get_stations(**self.query_params)
    def current(self):
        return self.inv.networks[self.net_idx], self.inv.networks[self.net_idx].stations[self.sta_idx]
    def next(self):
        self.sta_idx += 1
        if self.net_idx >= len(self.inv.networks):
            return self.__empty__
        while self.sta_idx >= len(self.inv.networks[self.net_idx].stations):
            self.net_idx += 1
            self.sta_idx = 0
            if self.net_idx >= len(self.inv.networks):
                return self.__empty__
        return self.inv.networks[self.net_idx], self.inv.networks[self.net_idx].stations[self.sta_idx]
    def prev(self):
        self.sta_idx -= 1
        while self.sta_idx < 0:
            self.net_idx -= 1
            if self.net_idx < 0:
                return self.__empty__
            self.sta_idx = len(self.inv.networks[self.net_idx].stations)-1
        return self.inv.networks[self.net_idx], self.inv.networks[self.net_idx].stations[self.sta_idx]
    def beginning(self):
        self.net_idx = 0
        self.sta_idx = -1
    def ending(self):
        self.net_idx = len(self.inv.networks)-1
        self.sta_idx = len(self.inv.networks[self.net_idx])
