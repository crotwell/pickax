
# to get some test data:
# curl -o JKYD.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JKYD&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# curl -o JSC.mseed 'https://service.iris.edu/fdsnws/dataselect/1/query?net=CO&sta=JSC&loc=00&cha=HHZ&starttime=2022-10-31T01:33:30&endtime=2022-10-31T01:34:30&format=miniseed&nodata=404'
# LE event Oct 31, 2022
# curl -o elgin.qml 'https://earthquake.usgs.gov/fdsnws/event/1/query?eventid=se60414656&format=quakeml'
station_code = "JKYD"
evt_qml = "elgin.qml"

def dosave(qmlevent, stream):
    station_code = stream[0].stats.station
    out_cat = obspy.Catalog([qmlevent])
    out_cat.write(f"{station_code}_pick.qml", format='QUAKEML')


st = obspy.read(f'{station_code}.mseed')
catalog = obspy.read_events(evt_qml)

p = PickSeis(st, qmlevent=catalog[0], finishFn=dosave)
p.draw()
# on space, dosave will be called

station_code = "JSC"
st = obspy.read(f'{station_code}.mseed')
catalog = obspy.read_events(evt_qml)
p = PickSeis(st, qmlevent=catalog[0], finishFn=dosave)
p.draw()
