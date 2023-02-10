import os
from obspy import Catalog
from pickax import PickAxConfig, merge_picks_to_catalog

# to get some test data, this uses an event in South Carolina,
# near Lugoff-Elgin on Oct 31, 2022
#
# curl -o BIRD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=BIRD&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JKYD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JKYD&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JSC.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JSC&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o elgin.qml 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=se60414656&format=quakeml'

me = "Jane Smith"
creation_info = CreationInfo(author=me, version="0.0.1")


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

# color picks by author
author_colors = {
    me: "lime",
    "Freddie Freeloader": "purple",
    "Minnie the Mooch": "seagreen",
}
def flagcolorFn(pick, arrival):
    print("color fn")
    color = None # none means use built in defaults, red and blue
    if pick is None and arrival is None:
        color = None
    elif arrival is not None:
        # usually means pick used in official location
        color = "blue"
    else:
        pick_author = ""
        if pick.creation_info.agency_id is not None:
            pick_author += pick.creation_info.agency_id+" "
        if pick.creation_info.author is not None:
            pick_author += pick.creation_info.author+ " "
        pick_author = pick_author.strip()
        if pick_author in author_colors:
            color = author_colors[pick_author]
        print(f"color fn {pick_author} -> {color}")
    return color


# remember who and where we are
curr_idx = 0
pickax = None

# function called on quit, next or prev, allows saving of picks however you wish
# here we save the quake as QuakeML, which will include the picks, and then
# load the next seismogram if possible
def dosave(qmlevent, stream, command, pickax):
    global curr_idx
    # first time through qmlevent will be None and stream will be empty
    if qmlevent is not None and len(stream) != 0:
        station_code = stream[0].stats.station
        out_cat = obspy.Catalog([qmlevent])
        out_cat.write(f"pick_elgin.qml", format='QUAKEML')
    if command == "next":
        curr_idx += 1
    elif command == "prev":
        curr_idx -= 1
    else:
        # quit
        return
    if curr_idx < 0:
        print(f"can't go before start: {curr_idx}")
        curr_idx = 0
    elif curr_idx < len(station_codes):
        print(f"load {curr_idx}  of {len(station_codes)}, {station_codes[curr_idx]}")
        if not os.path.exists(f'{station_codes[curr_idx]}.mseed'):
            print(f'file {station_codes[curr_idx]}.mseed does not seem to exist.')
            pickax.close()
            return
        st = obspy.read(f'{station_codes[curr_idx]}.mseed')
        preprocess(st)
        # could update both stream and Qml Event
        # pickax.update_data(st, catalog[0])
        # or just the stream if the event is the same
        pickax.update_data(st)
    else:
        pickax.close()

# helper function to check if files exist and start up PickAx
def pick_station(station_code, qmlevent_file):
    catalog = []
    if not os.path.exists(f'{qmlevent_file}'):
        print(f'file {qmlevent_file} does not seem to exist, skipping.')
    else:
        catalog = obspy.read_events(qmlevent_file)
    qmlevent = catalog[0] if len(catalog) > 0 else None

    saved_catalog = Catalog()
    saved_pick_file = 'pick_elgin.qml'
    if not os.path.exists(f'{saved_pick_file}'):
        print(f'file {saved_pick_file} does not seem to exist, skipping load picks.')
    else:
        saved_catalog = obspy.read_events(saved_pick_file)
        for oldquake in saved_catalog:
            merge_picks_to_catalog(oldquake, catalog, author=creation_info.author)

    pickax = PickAx(qmlevent=qmlevent,
                    config=pickax_config ,
                    )
    return pickax

# get ready and...
station_codes = ["JKYD", "JSC", "BIRD"]
evt_qml = "elgin.qml"


# Configure the tool
pickax_config = PickAxConfig()
pickax_config.creation_info = creation_info
pickax_config.finishFn=dosave
pickax_config.filters = filters
pickax_config.flagcolorFn = flagcolorFn

# start digging!
pickax = pick_station(station_codes[0], evt_qml)
