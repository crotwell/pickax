import os

# to get some test data, this uses an event in South Carolina,
# near Lugoff-Elgin on Oct 31, 2022
#
# curl -o BIRD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=BIRD&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JKYD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JKYD&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JSC.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JSC&loc=00&cha=HH?&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
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
        out_cat.write(f"{station_code}_pick.qml", format='QUAKEML')
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
def pick_station(station_code, qmlevent_file, creation_info):
    catalog = []
    if not os.path.exists(f'{qmlevent_file}'):
        print(f'file {qmlevent_file} does not seem to exist, skipping.')
    else:
        catalog = obspy.read_events(qmlevent_file)
    qmlevent = catalog[0] if len(catalog) > 0 else None

    pickax = PickAx(qmlevent=qmlevent,
                    finishFn=dosave,
                    creation_info = creation_info,
                    filters = filters, # allows toggling between fitlers
                    figsize=(10,8),
                    )
    return pickax

# get ready and...
station_codes = ["JKYD", "JSC", "BIRD"]
evt_qml = "elgin.qml"
info = CreationInfo(author="Jane Smith", version="0.0.1")
# start digging!
pickax = pick_station(station_codes[0], evt_qml, info)
