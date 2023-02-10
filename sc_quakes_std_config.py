import os
from obspy.clients.fdsn.header import FDSNNoDataException
from obspy.core.event.base import CreationInfo
from pickax import (
    PickAxConfig,
    FDSNQuakeIterator, FDSNStationIterator,
    FDSNSeismogramIterator,
    ThreeAtATime,
    CacheSeismogramIterator,
    merge_picks_to_catalog,
    merge_picks_to_quake,
    extractEventId,
    )
from obspy import Catalog

# create a few filters, will be able to toggle between them with the 'f' key
def bpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('bandpass', freqmin=1, freqmax=10.0, corners=1, zerophase=True)

def hpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('highpass', freq=1.0,  corners=1, zerophase=True)

def createStandardConfig(author="Jane Smith"):

    # Configure the tool
    pickax_config = PickAxConfig()
    pickax_config.creation_info = CreationInfo(author=author, version="0.0.1")
    pickax_config.author_colors = {
        author: "red",
        "Freddie Freeloader": "purple",
        "Minnie the Mooch": "seagreen",
    }

    # show prediceted travel times for these phases
    pickax_config.phase_list = ['P', 'S', 'p', 's']

    pickax_config.filters = [
        { "name": "bandpass 1 10", "fn": bpfilter},
        { "name": "highpass 1", "fn": hpfilter},
    ]
    return pickax_config
