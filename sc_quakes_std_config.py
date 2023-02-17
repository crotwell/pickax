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

def createStandardConfig(author=None):

    # Configure the tool
    pickax_config = PickAxConfig()
    pickax_config.creation_info = CreationInfo(author=author, version="0.0.1")
    # big list of color names at:
    # https://matplotlib.org/stable/gallery/color/named_colors.html
    pickax_config.author_colors = {
        "Dan Frost": "lime",
        "Chase Robinson": "seagreen",
        "Ashley Ford": "rebeccapurple",
        "Logan Zollinger": "maroon",
        "Philip Crotwell": "tomato",
    }

    # save default color-label function for picks
    default_pick_color_label_fn = pickax_config.pick_color_labelFn
    # create new color label function that uses existing, but appends version
    def pick_versionFn(pick, arrival):
        color, label = default_pick_color_label_fn(pick, arrival)
        ver = pick.creation_info.version if pick.creation_info.version is not None else ""
        label = f"{label} {ver}"
        return color, label
    # create new color label function that uses existing, but appends author
    def pick_versionFn(pick, arrival):
        color, label = default_pick_color_label_fn(pick, arrival)
        author = pick.creation_info.author if pick.creation_info.author is not None else ""
        label = f"{label} {author}"
        return color, label


    pickax_config.pick_color_labelFn = pick_versionFn

    # show prediceted travel times for these phases
    pickax_config.phase_list = ['P', 'S', 'p', 's']

    pickax_config.filters = [
        { "name": "bandpass 1 10", "fn": bpfilter},
        { "name": "highpass 1", "fn": hpfilter},
    ]
    return pickax_config
