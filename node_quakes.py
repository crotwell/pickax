import os
from obspy.clients.fdsn.header import FDSNNoDataException
from pickax import (
    PickAxConfig,
    FDSNQuakeIterator,
    StationXMLIterator,
    FDSNSeismogramIterator,
    FDSNStationIterator,
    ThreeAtATime,
    CacheSeismogramIterator,
    merge_picks_to_catalog,
    merge_picks_to_quake,
    extractEventId,
    )
from obspy import Catalog
from sc_quakes_std_config import createStandardConfig
from sc_quakes_std_dosave import create_dosaveFn
from node_iterate import load_nodes, NodeSacZips

# author info for picks, your name here...
me = "Jane Smith"
me = "Philip Crotwell"
all_picks_qml_file = "picks_sc_quakes.qml"
all_picks_qml_file = "all_picks.qml"

pickax_config = createStandardConfig(author=me)
pickax_config.creation_info.version="0.0.1"

# parameters for selecting earthquakes, server defaults to USGS
quake_query_params = {
    "start": "2023-01-18T00:00:00",
    "minlatitude":33,
    "maxlatitude":35,
    "minlongitude":-82,
    "maxlongitude":-80,
    "minmag": 1.0,
    "orderby": "time-asc",
}
quake_itr = FDSNQuakeIterator(quake_query_params)

# alternatively, load from existing QuakeML file
# quake_query_params = "my_sc_quakes.qml"

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

inventory = load_nodes("stn_node_all_update.txt")
#inv2 = FDSNStationIterator(sta_query_params).inv
#for n in inv2.networks:
#    inventory.networks.append(n)
station_itr = StationXMLIterator(inventory)


# alternatively, may be faster to preload all station,channels like:
# curl -o all_sc_stations.staxml 'https://service.iris.edu/fdsnws/station/1/query?net=CO,N4,US,TA&level=response&format=xml&maxlat=35.415&minlon=-83.487&maxlon=-78.257&minlat=31.867&includecomments=false&nodata=404'
# sta_query_params = "all_sc_stations.staxml"

# calculate time window from predicted traveltimes for phases and offsets
# origin is allowed as a phase name to base offsets on origin time of quake
seis_params = {
    "start_phases": "origin",
    "end_phases": "origin",
    "start_offset": -30,
    "end_offset": 120,
}
seis_itr = NodeSacZips(quake_itr, station_itr, "data")
pickax_config.finishFn=create_dosaveFn(quake_query_params=quake_itr,
                                       station_query_params=station_itr,
                                       seis_params=seis_itr,
                                       config=pickax_config,
                                       picks_file=all_picks_qml_file)


# start digging!
pickax = PickAx(config=pickax_config )
