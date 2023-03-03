
import os
from pathlib import Path
import zipfile
from zipfile import ZipFile
from obspy import Inventory, read_inventory
import obspy
from obspy import Stream
from obspy.taup import TauPyModel
from obspy.geodetics import locations2degrees
from obspy.core.inventory import Network, Station, Channel
from obspy.core.inventory import Equipment
from pickax import SeismogramIterator, QuakeIterator

def load_nodes(filename):
    all_sta = []
    with open(filename, 'r') as infile:
        head = infile.readline()
        for line in infile:
            items = line.split()
            if len(items) != 4:
                raise Exception("not 4 items in line")
            lat = float(items[2])
            lon  = float(items[1])
            elev = 70
            code = items[0]
            nodeid = items[3]
            station = Station(code, lat, lon, elev, description=nodeid)
            sensor = Equipment(serial_number=nodeid)
            station.channels = [
                                Channel("SHZ", "00", lat, lon, elev, 0, azimuth=0, dip=0, sample_rate=1/0.004),
                                Channel("SHN", "00", lat, lon, elev, 0, azimuth=0, dip=0, sample_rate=1/0.004),
                                Channel("SHE", "00", lat, lon, elev, 0, azimuth=0, dip=0, sample_rate=1/0.004)
                                ]
            for c in station.channels:
                c.sensor = sensor
            all_sta.append(station)
    return Inventory(networks = [Network("XX", stations=all_sta)])

def node_sac_file(quake, channel, datadir):
    stream = Stream()
    ymdh = quake.preferred_origin().time.strftime("%Y%m%d")

    print(f"zip glob: {ymdh}_M?.?-*.zip")
    zipfilelist = datadir.glob(f"{ymdh}_M?.?-*.zip")
    for zf in zipfilelist:
        with ZipFile(zf) as zip:
            globpat = f"*/{channel.sensor.serial_number}*.{channel.code[2]}.sac"
            for info in zip.infolist():
                if channel.sensor.serial_number in info.filename \
                        and info.filename.endswith(f".{channel.code[2]}.sac"):
                    with zip.open(info) as sacfile:
                        st = obspy.core.stream.read(sacfile, format="SAC")
                        stream = stream + st
    return stream

class NodeSacZips(SeismogramIterator):
    def __init__(self,
                 quake_itr,
                 station_itr,
                 datadir,
                 start_phases="origin", start_offset = 0,
                 end_phases="origin", end_offset=300,
                 debug=False):
        self.__empty__ = None, None, None, []
        self.debug = debug
        self.query_params = {}
        self.datadir = Path(datadir)
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
        waveforms = Stream()
        for c in sta.channels:
            waveforms += node_sac_file(quake, c, self.datadir)
        return net, sta, quake, waveforms

def main():
    all = load_nodes("stn_node_all_update.txt")
    print(len(all))


if __name__ == "__main__":
    main()
