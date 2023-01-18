import os
from obspy.clients.fdsn.header import FDSNNoDataException
from pickax import (
    FDSNQuakeIterator, FDSNStationIterator, FDSNSeismogramIterator,
    ThreeAtATime
    )

# helper function, perhaps to preprocess the stream before picking
def preprocess(stream, inv):
    stream.detrend()
    # deconvolution prefiltering, 10 sec to 45 Hz
    pre_filt = [0.02, 0.1, 45, 50]
    for tr in stream:
        tr.remove_response(inventory=inv, pre_filt=pre_filt, output="VEL", water_level=None)


# create a few filters, will be able to toggle between them with the 'f' key
def lpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('lowpass', freq=1.0,  corners=1, zerophase=True)

def bpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('bandpass', freqmin=1, freqmax=10.0, corners=1, zerophase=True)

def hpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('highpass', freq=1.0,  corners=1, zerophase=True)

filters = [
    { "name": "bandpass 1 10", "fn": bpfilter},
    { "name": "highpass 1", "fn": hpfilter},
]

pickax = None
debug = False

# function called on quit, next or prev, allows saving of picks however you wish
# here we save the quake as QuakeML, which will include the picks, and then
# load the next seismogram if possible
def dosave(qmlevent, stream, command):
    global pickax
    global seis_itr, sta_itr, quake_itr
    station_code = stream[0].stats.station
    out_cat = obspy.Catalog([qmlevent])
    out_cat.write(f"{station_code}_pick.qml", format='QUAKEML')
    all_pick_lines = pickax.display_picks(author=pickax.creation_info.author)
    if len(all_pick_lines) > 0:
        with open(f"{qmlevent.preferred_origin().time}_picks.txt", "a", encoding="utf-8") as outtxt:
            for line in all_pick_lines:
                outtxt.write(line)
    seis = [] # force while to run
    sta = "dummy"
    quake = "dummy"
    if command == "next":
        while len(seis) == 0 and sta is not None and quake is not None:
            net, sta, quake, seis = seis_itr.next()
    elif command == "prev":
        while len(seis) == 0 and sta is not None and quake is not None:
            net, sta, quake, seis = seis_itr.prev()
    else:
        # quit
        return

    if len(seis) == 0:
        print(f"No data for {net.code}_{sta.code} for event {quake.preferred_origin().time}...")
    elif sta is not None and quake is not None:
        all_chan = ",".join(list(map(lambda tr: tr.stats.channel, seis)))
        print(f"{len(seis)} {net.code}_{sta.code} {all_chan} {quake.preferred_origin().time}")
        preprocess(seis, sta_itr.inv)
        # could update both stream and Qml Event
        # pickax.update_data(st, catalog[0])
        # or just the stream if the event is the same
        pickax.update_data(seis, quake)
    else:
        print(f"close as {sta is None} {quake is None}")
        pickax.close()

# Load stations, events and seismograms
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
sta_itr = FDSNStationIterator(sta_query_params, debug=debug)


quake_query_params = {
    "start": "2021-12-27T00:00:00",
    "minlatitude":33,
    "maxlatitude":35,
    "minlongitude":-82,
    "maxlongitude":-80,
    "minmag": 3.0,
}
quake_itr = FDSNQuakeIterator(quake_query_params, debug=debug)

# use ThreeAtATime to separate by band/inst code, ie seismometer then strong motion
# at each station that has both
seis_itr = ThreeAtATime(FDSNSeismogramIterator(quake_itr, sta_itr, start_offset = -30, end_offset=120, debug=debug, timeout=15))
net, sta, quake, seis = seis_itr.next()
preprocess(seis, sta_itr.inv)
creation_info = CreationInfo(author="Jane Smith", version="0.0.1")
# start digging!
pickax = PickAx(seis,
                  qmlevent=quake,
                  finishFn=dosave,
                  creation_info = creation_info,
                  filters = filters, # allows toggling between fitlers
                  figsize=(10,8),
                  debug=True,
                  )
pickax.draw()