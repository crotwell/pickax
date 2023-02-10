import os
from obspy.clients.fdsn.header import FDSNNoDataException
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
from sc_quakes_std_config import createStandardConfig
from sc_quakes_std_dosave import create_dosaveFn

# author info for picks, your name here...
me = "Jane Smith"
all_picks_qml_file = "picks_sc_quakes.qml"

pickax_config = createStandardConfig(author=me)
pickax_config.creation_info.version="0.0.1"

# parameters for selecting earthquakes, server defaults to USGS
quake_query_params = {
    "start": "2021-12-27T00:00:00",
    "minlatitude":33,
    "maxlatitude":35,
    "minlongitude":-82,
    "maxlongitude":-80,
    "minmag": 3.0,
    "orderby": "time-asc",
}
# station/channel parameters, server defaults to IRIS
sta_query_params = {
    "network": "CO,TA,N4,US",
    "start": "2021-12-27T00:00:00",
    "minlatitude":32,
    "maxlatitude":35,
    "minlongitude":-82,
    "maxlongitude":-80,
    "channel": "HH?,HN?",
    "level": "response",
}

# calculate time window from predicted traveltimes for phases and offsets
# origin is allowed as a phase name to base offsets on origin time of quake
seis_params = {
    "start_phases": "origin",
    "end_phases": "origin",
    "start_offset": -30,
    "end_offset": 120,
}

pickax_config.finishFn=create_dosaveFn(quake_query_params,
                                       sta_query_params,
                                       seis_params,
                                       pickax_config,
                                       picks_file=all_picks_qml_file)


# start digging!
pickax = PickAx(config=pickax_config )
