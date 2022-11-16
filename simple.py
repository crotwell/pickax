
# to get some test data:
# curl -o JKYD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JKYD&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JSC.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JSC&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# LE event Oct 31, 2022
# curl -o elgin.qml 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=se60414656&format=quakeml'

def preprocess(stream):
    stream.detrend()
    stream.filter('highpass', freq=1.0,  corners=1, zerophase=True)

def dosave(qmlevent, stream):
    station_code = stream[0].stats.station
    out_cat = obspy.Catalog([qmlevent])
    out_cat.write(f"{station_code}_pick.qml", format='QUAKEML')


def pick_station(station_code, qmlevent, creation_info):
    st = obspy.read(f'{station_code}.mseed')
    preprocess(st)

    pickaxe = PickSeis(st, qmlevent=qmlevent, finishFn=dosave)
    pickaxe.creation_info = info
    pickaxe.draw()
    return pickaxe
    # on q, dosave will be called

station_codes = ["JKYD", "JSC"]
evt_qml = "elgin.qml"
catalog = obspy.read_events(evt_qml)
info = CreationInfo(author="Jane Smith", version="0.0.1")

pick_station(station_codes[0], catalog[0], info)
