from pickax import FDSNQuakeIterator, FDSNStationIterator, FDSNSeismogramIterator

def test_station():
    query_params = {
        "network": "CO",
        "station": "BIRD,JSC,JKYD",
        "channel": "HHZ,HNZ"
    }
    itr = FDSNStationIterator(query_params, debug=True)
    net, sta = itr.next()
    while sta is not None:
        print(f"{net.code}_{sta.code}")
        net, sta = itr.next()

def test_quake():
    query_params = {
        "start": "2022-11-24T16:00:00",
        "end":"2022-11-24T17:00:00",
        "minlatitude":34,
        "maxlatitude":35,
        "minlongitude":-81,
        "maxlongitude":-79
    }
    itr = FDSNQuakeIterator(query_params, debug=True)
    q = itr.next()
    while q is not None:
        o = q.preferred_origin()
        print(f"{o}")
        q = itr.next()

def test_seismogram():
    sta_query_params = {
        "network": "CO",
        "station": "BIRD,JSC,JKYD",
        "channel": "HHZ,HNZ"
    }
    sta_itr = FDSNStationIterator(sta_query_params)

    quake_query_params = {
        "start": "2022-11-24T16:00:00",
        "end":"2022-11-24T17:00:00",
        "minlatitude":34,
        "maxlatitude":35,
        "minlongitude":-81,
        "maxlongitude":-79
    }
    quake_itr = FDSNQuakeIterator(quake_query_params)

    seis_itr = FDSNSeismogramIterator(quake_itr, sta_itr, debug=True, timeout=15)
    net, sta, quake, seis = seis_itr.next()
    while sta is not None and quake is not None:
        print(f"{len(seis)} {net.code}_{sta.code} {quake.preferred_origin().time}")
        net, sta, quake, seis = seis_itr.next()


def main():
    test_station()
    test_quake()
    test_seismogram()
    print("Done")

if __name__ == "__main__":
    main()
