import os
from pickax import FDSNQuakeIterator, FDSNStationIterator, FDSNSeismogramIterator

# to get some test data, this uses an event in South Carolina,
# near Lugoff-Elgin on Oct 31, 2022
#
# curl -o JKYD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JKYD&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JSC.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JSC&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o elgin.qml 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=se60414656&format=quakeml'

# helper function, perhaps to preprocess the stream before picking
def preprocess(stream):
    stream.detrend()

# create a few filters, will be able to toggle between them with the 'f' key
def lpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('lowpass', freq=1.0,  corners=1, zerophase=True)

def bpfilter(original_stream, current_stream, prevFilter, idx):
    return original_stream.filter('bandpass', freqmin=.5, freqmax=5.0, corners=1, zerophase=True)

def hpfilter(original_stream, current_stream, prevFilter, idx):
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
def dosave(qmlevent, stream, command):
    global pickax
    global seis_itr
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
sta_query_params = {
    "network": "CO",
    "station": "BIRD,JSC,JKYD",
    "channel": "HH?,HNZ"
}
sta_itr = FDSNStationIterator(sta_query_params, debug=debug)

quake_query_params = {
    "start": "2022-11-24T16:00:00",
    "end":"2022-12-11T17:00:00",
    "minlatitude":34,
    "maxlatitude":35,
    "minlongitude":-81,
    "maxlongitude":-79
}
quake_itr = FDSNQuakeIterator(quake_query_params, debug=debug)

seis_itr = FDSNSeismogramIterator(quake_itr, sta_itr, debug=debug, timeout=15)
net, sta, quake, seis = seis_itr.next()
preprocess(seis)
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
