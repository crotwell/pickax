from abc import ABC, abstractmethod
from obspy import UTCDateTime, Catalog, read_events
from obspy.clients.fdsn.header import FDSNException
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.clients.fdsn import Client
from .pick_util import reloadQuakeMLWithPicks, extractEventId

class QuakeIterator(ABC):
    def __init__(self):
        self.quakes = Catalog([])
    @abstractmethod
    def next(self):
        return None
    @abstractmethod
    def prev(self):
        return None
    @abstractmethod
    def beginning(self):
        pass

class QuakeMLFileIterator(QuakeIterator):
    def __init__(self, file):
        self.quakes = read_events(file)
    def next(self):
        self.batch_idx += 1
        if self.batch_idx >= len(self.quakes):
            #self.next_batch()
            return None
        quake = self.quakes[self.batch_idx]
        return quake
    def prev(self):
        self.batch_idx -= 1
        if self.batch_idx < 0:
            self.batch_idx = -1
            return None
        return self.quakes[self.batch_idx]
    def beginning(self):
        self.batch_idx = -1

class FDSNQuakeIterator(QuakeIterator):
    def __init__(self, query_params, days_step=30, dc_name="USGS", debug=False):
        self.debug = debug
        self.dc_name = dc_name
        self.query_params = dict(query_params)
        if 'orderby' not in self.query_params:
            self.query_params['orderby'] = 'time-asc'
        self.days_step = days_step
        self.__curr_end = UTCDateTime(query_params["start"]) if query_params["start"] else UTCDateTime()
        self.quakes = self.next_batch()
        self.batch_idx = -1
    def next_batch(self):
        try:
            client = Client(self.dc_name, debug=self.debug)
            return client.get_events(**self.query_params)
        except FDSNNoDataException:
            # return empty catalog instaed of exception
            return Catalog([])
    def next_batch_step(self):
        client = Client(self.dc_name, debug=self.debug)
        t1 = self.__curr_end
        t2 = t1 + self.days_step*86400
        step_query_params = dict(self.query_params)
        step_query_params['start'] = t1
        step_query_params['end'] = t2
        try:
            self.quakes = client.get_events(**step_query_params)
        except FDSNNoDataException:
            # return empty catalog instaed of exception
            self.quakes =  Catalog([])
        end = UTCDateTime(query_params["end"])
        if len(self.quakes) == 0 and step_query_params['end'] < end:
            return self.next_batch_step()
        return self.quakes
    def next(self):
        self.batch_idx += 1
        if self.batch_idx >= len(self.quakes):
            #self.next_batch()
            return None
        quake = self.quakes[self.batch_idx]
        if self.dc_name == "USGS":
            print(f"Attempt to reload with picks {extractEventId(quake)}")
            quake = reloadQuakeMLWithPicks(quake, host=self.dc_name, debug=self.debug)
            self.quakes[self.batch_idx] = quake
        return quake
    def prev(self):
        self.batch_idx -= 1
        if self.batch_idx < 0:
            self.batch_idx = -1
            return None
        return self.quakes[self.batch_idx]
    def beginning(self):
        self.batch_idx = -1
