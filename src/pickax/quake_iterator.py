from abc import ABC, abstractmethod
from obspy import UTCDateTime, Catalog, read_events
from obspy.clients.fdsn.header import FDSNException
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.clients.fdsn import Client
from .pick_util import (
    reloadQuakeMLWithPicks,
    extractEventId,
    merge_picks_to_quake
    )

from pathlib import Path
import re
import os

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
    def all(self):
        return None

class QuakeMLFileIterator(QuakeIterator):
    def __init__(self, file):
        self.quakes = read_events(file)
        self.batch_idx = -1
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
    def all(self):
        return self.quakes


class QuakeMLDirectoryIterator(QuakeIterator):
    """
    Looks for QuakeML files like *.qml and iterates the quakes in
    each file.
    """
    def __init__(self, dir, pattern="**/*.qml"):
        self.root_dir = Path(dir)
        self.pattern = pattern
        self.qmlfiles = list(root_dir.glob(pattern))

        self.quakes = Catalog()
        self.q_to_dir = dict()
        for file in self.qmlfiles:
            dir_quakes = read_events(file)
            self.quakes.extend(dir_quakes)
            for q in dir_quakes:
                self.q_to_dir[q.resource_id] = file
        self.batch_idx = -1
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
    def all(self):
        return self.quakes
    def quakedir(self, quake):
        return self.q_to_dir[quake.resource_id]

class FDSNQuakeIterator(QuakeIterator):
    def __init__(self, query_params, days_step=30, dc_name="USGS", debug=False):
        self.debug = debug
        self.dc_name = dc_name
        self._client = None
        self.query_params = dict(query_params)
        if 'orderby' not in self.query_params:
            self.query_params['orderby'] = 'time-asc'
        self.days_step = days_step
        self.__curr_end = UTCDateTime(query_params["start"]) if query_params["start"] else UTCDateTime()
        self.quakes = self.next_batch()
        self.batch_idx = -1
    @property
    def client(self):
        if self._client is None:
            self._client = Client(self.dc_name, _discover_services=False, debug=self.debug)
        return self._client
    def next_batch(self):
        # careful if implement batching, as all() will be wrong in that case?
        try:
            return self.client.get_events(**self.query_params)
        except FDSNNoDataException:
            # return empty catalog instaed of exception
            return Catalog([])
    def next_batch_step(self):
        t1 = self.__curr_end
        t2 = t1 + self.days_step*86400
        step_query_params = dict(self.query_params)
        step_query_params['start'] = t1
        step_query_params['end'] = t2
        try:
            self.quakes = self.client.get_events(**step_query_params)
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
            quake = reloadQuakeMLWithPicks(quake, client=self.client, debug=self.debug)
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
    def all(self):
        return self.quakes

class CachedPicksQuakeItr(QuakeIterator):
    def __init__(self, quake_itr, cachedir='by_eventid'):
        self.quake_itr = quake_itr
        self.quakes = self.quake_itr.quakes
        self.cachedir = Path(cachedir)
        self.bad_file_chars_pat = re.compile(r'[\s:\(\)/]+')
    def next(self):
        q = self.quake_itr.next()
        return self.reload_picks(q)
    def prev(self):
        q = self.quake_itr.prev()
        return self.reload_picks(q)
    def beginning(self):
        return self.quake_itr.beginning()
    def reload_picks(self, quake):
        # look for picks in cache dir
        if quake is None:
            return quake
        eid = extractEventId(quake)
        qfile = f"eventid_{re.sub(self.bad_file_chars_pat, '_', eid)}.qml"
        qpath=  Path(self.cachedir / qfile)
        if qpath.exists():
            pick_quake = read_events(qpath)[0]
            merge_picks_to_quake(pick_quake, quake)
        return quake
    def all(self):
        return self.quake_itr.all()
