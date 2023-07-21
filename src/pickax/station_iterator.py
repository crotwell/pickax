from abc import ABC, abstractmethod
from obspy.clients.fdsn import Client
from obspy import Inventory, read_inventory
from obspy.clients.fdsn.header import FDSNNoDataException
from pathlib import Path


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
    def all_stations(self):
        return None

class StationXMLIterator(StationIterator):
    def __init__(self, inv, debug=False):
        self.debug = debug
        self.__empty__ = None, None
        self.net_idx = 0
        self.sta_idx = -1
        self.inv = inv
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
        self.sta_idx = len(self.inv.networks[self.net_idx].stations)
    def __len__(self):
        count = 0
        for n in self.inv.networks:
            count += len(n.stations)
        return count
    def all_stations(self):
        all_sta = []
        for n in self.inv.networks:
            for s in n.stations:
                all_sta.append(s)
        return all_sta


class StationXMLFileIterator(StationXMLIterator):
    def __init__(self, filename):
        super().__init__(read_inventory(filename))

class FDSNStationIterator(StationXMLIterator):
    def __init__(self, query_params, dc_name="IRIS", debug=False):
        self.debug = debug
        self.__empty__ = None, None
        self.dc_name = dc_name
        self.query_params = dict(query_params)
        if "level" not in query_params:
            self.query_params["level"] = "channel"
        super().__init__(self.__load__())

    def __load__(self):
        try:
            client = Client(self.dc_name, _discover_services=False, debug=self.debug)
            return client.get_stations(**self.query_params)
        except FDSNNoDataException:
            return Inventory()

class StationXMLDirectoryIterator(StationXMLIterator):
    def __init__(self, dir, pattern="**/*.xml"):
        self.root_dir = Path(dir)
        self.pattern = pattern
        self.stamlfiles = list(self.root_dir.glob(pattern))
        self.curr_itr = None
        self.idx = -1
        self.net = None
        self.sta = None
    def next(self):
        net = None
        sta = None
        while sta is None and self.idx < len(self.stamlfiles):
            if self.curr_itr is None:
                self.idx += 1
                if self.idx < len(self.stamlfiles):
                    self.curr_itr = StationXMLFileIterator(self.stamlfiles[self.idx])
                else:
                    break
            net, sta = self.curr_itr.next()
            if sta is None:
                self.curr_itr = None
            else:
                self.inv = self.curr_itr.inv
        return net, sta
    def prev(self):
        net = None
        sta = None
        while sta is None and self.idx > 0:
            if self.curr_itr is None:
                self.idx -= 1
                self.curr_itr = StationXMLFileIterator(self.stamlfiles[self.idx])
            net, sta = self.curr_itr.prev()
            if sta is None:
                self.curr_itr = None
        return net, sta
    def beginning(self):
        self.idx = -1
        self.curr_itr = None
    def ending(self):
        net = None
        sta = None
        self.idx = len(self.stamlfiles)-1
        self.curr_itr = StationXMLFileIterator(self.stamlfiles[self.idx])
        self.curr_itr.ending()

def channel_from_sac(tr):
    lat = 0
    lon = 0
    elev = 0
    depth = 0
    az = 0
    dip = 0
    if sac in tr.stats:
        lat = tr.stats.sac['stla']
        lon = tr.stats.sac['stlo']
        elev = tr.stats.sac['stel']
        az = tr.stats.sac['cmpaz']
        dip = -1*tr.stats.sac['cmpinc']

    channel = Channel(tr.channel, tr.location, lat, lon, elev, depth, azimuth=az, dip=dip, sample_rate=tr.sample_rate)
    station = Station(tr.station, lat, lon, elev, channels = [ channel ])
    network = Network(tr.network, stations=[ station ])
    return network
