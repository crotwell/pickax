from abc import ABC, abstractmethod
from collections import deque
from obspy.clients.fdsn import Client
from obspy.taup import TauPyModel
from obspy.geodetics import locations2degrees
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.core import Stream


class SeismogramIterator(ABC):
    def __init__(self):
        self.__empty__ = None, None, None, []
    @abstractmethod
    def next(self):
        return self.__empty__
    @abstractmethod
    def prev(self):
        return self.__empty__

class CacheSeismogramIterator(SeismogramIterator):
    """
    Very simple cache, remembers prev, curr and next data
    for up to size items
    """
    def __init__(self, sub_itr, size=10):
        self.sub_itr = sub_itr
        self.size = size
        self.__curr_data__ = None
        self.__prev_cache__ = deque([], size)
        self.__next_cache__ = deque([], size)
    def next(self):
        if self.__curr_data__ is not None:
            self.__prev_cache__.append(self.__curr_data__)
        if len(self.__next_cache__) > 0:
            self.__curr_data__ = self.__next_cache__.pop()
        else:
            self.__curr_data__ = self.sub_itr.next()
        return self.__curr_data__
    def prev(self):
        if self.__curr_data__ is not None:
            self.__next_cache__.append(self.__curr_data__)
        if len(self.__prev_cache__) > 0:
            self.__curr_data__ = self.__prev_cache__.pop()
        else:
            self.__curr_data__ = self.sub_itr.prev()
        return self.__curr_data__


class FDSNSeismogramIterator(SeismogramIterator):
    def __init__(self,
                 quake_itr,
                 station_itr,
                 dc_name="IRIS",
                 start_phases="origin", start_offset = 0,
                 end_phases="origin", end_offset=300,
                 debug=False, timeout=30):
        self.__empty__ = None, None, None, []
        self.debug = debug
        self.timeout = timeout
        self.query_params = {}
        self.dc_name = dc_name
        self.quake_itr = quake_itr
        self.station_itr = station_itr
        self.curr_quake = quake_itr.next()
        self.start_phases = start_phases
        self.start_offset = start_offset
        self.end_phases = end_phases
        self.end_offset = end_offset
        self.taup_model = TauPyModel(model="ak135")
    def next(self):
        if self.curr_quake is None:
            return self.__empty__
        net, sta = self.station_itr.next()
        if sta is None:
            quake = self.quake_itr.next()
            if quake is None:
                return self.__empty__
            self.curr_quake = quake
            self.station_itr.beginning()
            net, sta = self.station_itr.next()
        if sta is None or self.curr_quake is None:
            return self.__empty__
        return self.__load_seismograms__(net, sta, self.curr_quake, self.query_params)
    def prev(self):
        if self.curr_quake is None:
            return self.__empty__
        net, sta = self.station_itr.prev()
        if sta is None:
            self.curr_quake = self.quake_itr.prev()
            self.station_itr.ending()
            net, sta = self.station_itr.prev()
            if self.curr_quake is None:
                return self.__empty__

        if sta is None or self.curr_quake is None:
            return self.__empty__
        return self.__load_seismograms__(net, sta, self.curr_quake, self.query_params)
    def __load_seismograms__(self, net, sta, quake, query_params={}):
        if len(sta.channels) == 0:
            return []
        client = Client(self.dc_name, debug=self.debug, timeout=self.timeout)
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
        waveforms = None
        try:
            waveforms = client.get_waveforms(net.code, sta.code, ",".join(locs), ",".join(chans), s_time, e_time)
        except FDSNNoDataException:
            waveforms = []
        return net, sta, quake, waveforms

class ThreeAtATime(SeismogramIterator):
    """
    Iterates over a sub-SeismogramIterator grouping the resulting seismograms
    into three-at-a-time components of motion. So a station with a seismometer
    and a strong motion would be split into 2 iterations, first the HHZ, HHN, HHE
    channels and then the HNZ, HNN, HNE channels.
    """
    def __init__(self, sub_itr):
        self.sub_itr = sub_itr
        self.sub_waveforms = []
        self.sub_idx = -1
        self.cur_net = None
        self.cur_sta = None
        self.cur_quake = None
    def split_3c(self, net, sta, quake, waveforms):
        self.sub_waveforms = []
        self.sub_idx = -1
        self.cur_net = net
        self.cur_sta = sta
        self.cur_quake = quake
        for tr in waveforms:
            found = False
            for sub_st in self.sub_waveforms:
                if sub_st[0].stats.channel[0] == tr.stats.channel[0] and \
                        sub_st[0].stats.channel[1] == tr.stats.channel[1]:
                    # same band and inst codes
                    sub_st.append(tr)
                    found = True
                    break
            if not found:
                self.sub_waveforms.append(Stream(traces=[tr]))
    def next(self):
        self.sub_idx += 1
        if len(self.sub_waveforms) > self.sub_idx:
            return self.cur_net, self.cur_sta, self.cur_quake, self.sub_waveforms[self.sub_idx]
        # load next batch
        self.split_3c(*self.sub_itr.next())
        self.sub_idx = 0
        if len(self.sub_waveforms) > self.sub_idx:
            return self.cur_net, self.cur_sta, self.cur_quake, self.sub_waveforms[self.sub_idx]
        else:
            return self.cur_net, self.cur_sta, self.cur_quake, []
    def prev(self):
        self.sub_idx -= 1
        if self.sub_idx >= 0:
            return self.cur_net, self.cur_sta, self.cur_quake, self.sub_waveforms[self.sub_idx]
        # load next batch
        self.split_3c(*self.sub_itr.prev())
        self.sub_idx = len(self.sub_waveforms)-1
        if self.sub_idx >= 0:
            return self.cur_net, self.cur_sta, self.cur_quake, self.sub_waveforms[self.sub_idx]
        else:
            return self.cur_net, self.cur_sta, self.cur_quake, []
