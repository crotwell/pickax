from abc import ABC, abstractmethod
from obspy.clients.fdsn import Client
from obspy.taup import TauPyModel
from obspy.geodetics import locations2degrees

class SeismogramIterator(ABC):
    def __init__(self):
        self.__empty__ = None, None, None, []
    @abstractmethod
    def next(self):
        return self.__empty__
    @abstractmethod
    def prev(self):
        return self.__empty__

class FDSNSeismogramIterator(SeismogramIterator):
    def __init__(self, quake_itr, station_itr, dc_name="IRIS", start_phases="origin", start_offset = 0, end_phases="origin", end_offset=300, debug=False):
        self.debug = debug
        self.query_params = {}
        self.dc_name = dc_name
        self.quake_itr = quake_itr
        self.station_itr = station_itr
        self.curr_quake = None
        self.start_phases = start_phases
        self.start_offset = start_offset
        self.end_phases = end_phases
        self.end_offset = end_offset
        self.taup_model = TauPyModel(model="ak135")
    def next(self):
        if self.curr_quake is None:
            self.curr_quake = self.quake_itr.next()
            if self.curr_quake is None:
                return self.__empty__
        net, sta = self.station_itr.next()
        while sta is None:
            self.station_itr.beginning()
            self.curr_quake = self.quake_itr.next()
        if sta is None or self.curr_quake is None:
            return self.__empty__
        return self.__load_seismograms__(net, sta, self.curr_quake, self.query_params)
    def prev(self):
        if self.curr_quake is None:
            return self.__empty__
        net, sta = self.station_itr.prev()
        while sta is None and self.curr_quake is not None:
            self.curr_quake = self.quake_itr.prev()
            self.station_itr.ending()
            sta = self.station_itr.prev()

        if sta is None or self.curr_quake is None:
            return self.__empty__
        return self.__load_seismograms__(new, sta, self.curr_quake, self.query_params)
    def __load_seismograms__(self, net, sta, quake, query_params={}):
        if len(sta.channels) == 0:
            return []
        client = Client(self.dc_name, debug=self.debug)
        origin = quake.preferred_origin()
        if origin is None:
            return self.__empty__
        dist_deg = locations2degrees(sta.latitude, sta.longitude, origin.latitude, origin.longitude)
        s_time = origin.time + self.start_offset
        if self.start_phases != "origin":
            arrivals = model.get_travel_times(source_depth_in_km=origin.depth/1000,
                                      distance_in_degree=dist_deg,
                                      phase_list=self.start_phases.split(","))
            if len(arrivals) == 0:
                return self.__empty__
            s_time = s_time + arrivals[0].time
        e_time = origin.time + self.end_offset
        if self.end_phases != "origin":
            arrivals = model.get_travel_times(source_depth_in_km=origin.depth/1000,
                                      distance_in_degree=dist_deg,
                                      phase_list=self.end_phases.split(","))
            if len(arrivals) == 0:
                return self.__empty__
            e_time = e_time + arrivals[0].time
        locs = set()
        chans = set()
        for c in sta.channels:
            locs.add(c.location_code)
            chans.add(c.code)
        return net, sta, quake, client.get_waveforms(net.code, sta.code, ",".join(locs), ",".join(chans), s_time, e_time)
