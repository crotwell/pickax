from abc import ABC, abstractmethod
from obspy import UTCDateTime
from obspy.clients.fdsn import Client
from .pick_util import reloadQuakeMLWithPicks, extractEventId

class QuakeIterator(ABC):
    def __init__(self):
        self.quakes = []
    @abstractmethod
    def next(self):
        return None
    @abstractmethod
    def prev(self):
        return None
    @abstractmethod
    def beginning(self):
        pass

class FDSNQuakeIterator(QuakeIterator):
    def __init__(self, query_params, days_step=30, dc_name="USGS", debug=False):
        self.debug = debug
        self.dc_name = dc_name
        self.query_params = dict(query_params)
        self.days_step = days_step
        self.__curr_end = UTCDateTime(query_params["start"]) if query_params["start"] else UTCDateTime()
        self.quakes = self.next_batch()
        self.batch_idx = -1
    def next_batch(self):
        client = Client(self.dc_name, debug=self.debug)
        return client.get_events(**self.query_params)
    def next_batch_step(self):
        client = Client(self.dc_name)
        t1 = self.__curr_end
        t2 = t1 + self.days_step*86400
        step_query_params = dict(self.query_params)
        step_query_params['start'] = t1
        step_query_params['end'] = t2
        self.quakes = client.get_events(**step_query_params)
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
            quake = reloadQuakeMLWithPicks(quake)
            self.quakes[self.batch_idx] = quake
        return quake
    def prev(self):
        self.batch_idx -= 1
        if self.batch_idx < 0:
            return None
        return self.quakes[self.batch_idx]
    def beginning(self):
        self.batch_idx = -1
