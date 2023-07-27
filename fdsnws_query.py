import os
from pickax import (
    PickAxConfig,
    FDSNQuakeIterator, FDSNStationIterator,
    FDSNSeismogramIterator,
    CacheSeismogramIterator
    )

# author info for picks, your name here...
creation_info = CreationInfo(author="Jane Smith", version="0.0.1")

# show prediceted travel times for these phases
phase_list = ['P', 'S', 'p', 's']

# parameters for selecting earthquakes, server defaults to USGS
sta_query_params = {
    "network": "CO",
    "station": "BIRD,JSC,JKYD",
    "channel": "HH?,HNZ",
}
# station/channel parameters, server defaults to IRIS
quake_query_params = {
    "start": "2022-11-24T16:00:00",
    "end": "2022-12-11T17:00:00",
    "minlatitude": 34,
    "maxlatitude": 35,
    "minlongitude": -81,
    "maxlongitude": -79,
}
# calculate time window from predicted traveltimes for phases and offsets
# origin is allowed as a phase name to base offsets on origin time of quake
seis_params = {
    "start_phases": "origin",
    "end_phases": "origin",
    "start_offset": -30,
    "end_offset": 120,
}


# helper function, perhaps to preprocess the stream before picking
def preprocess(stream):
    # check for preprocessed to see if already done
    if "preprocessed" not in stream[0].stats:
        stream.detrend()
        for tr in stream:
            # remind us we have seen this before
            tr.stats["preprocessed"] = True

# create a few filters, will be able to toggle between them with the 'f' key
def lpfilter(original_stream, current_stream, prevFilter, idx, inv, quake):
    return original_stream.filter('lowpass', freq=1.0,  corners=1, zerophase=True)

def bpfilter(original_stream, current_stream, prevFilter, idx, inv, quake):
    return original_stream.filter('bandpass', freqmin=.5, freqmax=5.0, corners=1, zerophase=True)

def hpfilter(original_stream, current_stream, prevFilter, idx, inv, quake):
    return original_stream.filter('highpass', freq=1.0,  corners=1, zerophase=True)

filters = [
    { "name": "lowpass_1", "fn": lpfilter},
    { "name": "bandpass", "fn": bpfilter},
    { "name": "highpass", "fn": hpfilter},
]

pickax = None
debug = False

# function called on quit, next or prev, allows saving of picks however you wish
# here we save the quake as QuakeML, which will include the picks, and then
# load the next seismogram if possible
def dosave(qmlevent, stream, command, pickax):
    global seis_itr
    # first time through qmlevent will be None and stream will be empty
    if qmlevent is not None and len(stream) != 0:
        station_code = stream[0].stats.station
        out_cat = obspy.Catalog([qmlevent])
        out_cat.write(f"{station_code}_pick.qml", format='QUAKEML')
    if command == "next":
        net, sta, quake, seis = seis_itr.next()
    elif command == "prev":
        net, sta, quake, seis = seis_itr.prev()
    else:
        # quit
        return
    if sta is not None and quake is not None:
        print(f"{len(seis)} {net.code}_{sta.code} {quake.preferred_origin().time}")
        preprocess(seis)
        # could update both stream and Qml Event
        # pickax.update_data(st, catalog[0])
        # or just the stream if the event is the same
        pickax.update_data(seis, quake)
    else:
        print(f"close as {sta is None} {quake is None}")
        pickax.close()

# Load stations, events and seismograms
sta_itr = FDSNStationIterator(sta_query_params, debug=debug)

quake_itr = FDSNQuakeIterator(quake_query_params, debug=debug)

seis_itr = FDSNSeismogramIterator(quake_itr, sta_itr, **seis_params, debug=debug, timeout=15)
seis_itr = CacheSeismogramIterator(seis_itr)

pickax_config = PickAxConfig()
pickax_config.finishFn = dosave
pickax_config.creation_info  = creation_info
pickax_config.filters = filters
pickax_config.seismogram_itr = seis_itr
pickax_config.phase_list = phase_list
pickax_config.debug = True
# start digging!
pickax = PickAx(config = pickax_config)
