import os
from obspy.clients.fdsn.header import FDSNNoDataException
from pickax import (
    PickAxConfig,
    FDSNQuakeIterator, FDSNStationIterator,
    FDSNSeismogramIterator,
    StationIterator,
    StationXMLFileIterator,
    StationXMLIterator,
    ThreeAtATime,
    CacheSeismogramIterator,
    merge_picks_to_catalog,
    merge_picks_to_quake,
    extractEventId,
    QuakeMLFileIterator,
    QuakeIterator,
    CachedPicksQuakeItr,
    SeismogramIterator
    )
from obspy import Catalog, read_events, Inventory


def create_dosaveFn(quake_query_params, station_query_params, seis_params, config=None, picks_file="picks_sc_quakes.qml"):
    if config is None:
        config = PickAxConfig()
    # Load stations, events and seismograms
    if station_query_params is None:
        sta_itr = None
    elif isinstance(station_query_params, StationIterator):
        sta_itr = station_query_params
    elif isinstance(station_query_params, Inventory):
        sta_itr = StationXMLIterator(station_query_params)
    elif isinstance(station_query_params, (str, os.PathLike)):
        # this loads from local file
        sta_itr = StationXMLFileIterator(station_query_params)
    else:
        # this loads stations/channels from remote server
        sta_itr = FDSNStationIterator(station_query_params, debug=config.debug)

    if quake_query_params is None:
        quake_itr = None
    elif isinstance(quake_query_params, QuakeIterator):
        quake_itr = CachedPicksQuakeItr(quake_query_params, cachedir="../by_eventid")
    elif isinstance(quake_query_params, (str, os.PathLike)):
        # this loads from local file
        quake_itr = CachedPicksQuakeItr(QuakeMLFileIterator(quake_query_params), cachedir="../by_eventid")
    else:
        # this loads quakes from remote server
        quake_itr = FDSNQuakeIterator(quake_query_params, debug=config.debug)

    if isinstance(seis_params, SeismogramIterator):
        seis_itr = seis_params
        if quake_itr is None:
            quake_itr = seis_itr.quake_iterator()
            print(f"Set quake_itr from seis_itr: {quake_itr}")
        if sta_itr is None:
            sta_itr = seis_itr.station_iterator()
            print(f"Set sta_itr from seis_itr: {sta_itr}")
    else:
        seis_itr = FDSNSeismogramIterator(quake_itr, sta_itr, debug=config.debug, **seis_params)
    # use ThreeAtATime to separate by band/inst code, ie seismometer then strong motion
    # at each station that has both
    seis_itr = ThreeAtATime(seis_itr)
    # cache make prev/next a bit faster if data is already here
    seis_itr = CacheSeismogramIterator(seis_itr)
    if config is not None:
        config.seismogram_itr = seis_itr

    print(f"Load station metadata...")
    try:
        print(f"Networks: {len(sta_itr.inv.networks)}, Stations: {len(sta_itr)}")
    except AttributeError:
        print("catch AttributeError")
        print(f"Networks: -, Stations: -")
    print(f"Load earthquakes...")
    print(f"Number of quakes: {len(quake_itr.quakes)}")

    # helper function, perhaps to preprocess the stream before picking
    def preprocess(stream, inv):
        PREPROC_KEY = "preprocessed"
        if PREPROC_KEY not in stream[0].stats:
            stream.detrend()
            # deconvolution prefiltering, 10 sec to 45 Hz
            pre_filt = [0.02, 0.1, 45, 50]
            for tr in stream:
                try:
                    if PREPROC_KEY not in tr.stats or not tr.stats[PREPROC_KEY]:
                        tr.remove_sensitivity(inv)
                        #tr.remove_response(inventory=inv, pre_filt=pre_filt, output="VEL", water_level=None)
                        tr.stats[PREPROC_KEY] = True
                except Exception as e:
                    print("Warn: unable to remove response for "+tr.id)
                    tr.stats[PREPROC_KEY] = True
                    break

    # function called on quit, next or prev, allows saving of picks however you wish
    # here we save the quake as QuakeML, which will include the picks, and then
    # load the next seismogram if possible
    def dosave(qmlevent, stream, command, pickax):
        saved_catalog = None
        # set overall inventory if not already set
        if pickax.inventory is None:
            try:
                pickax.inventory = sta_itr.inv
            except AttributeError:
                print("catch AttributeError")
                pickax.inventory = None
        # first time through qmlevent will be None and stream will be empty
        if qmlevent is not None and len(stream) != 0:
            # save new picks to picks_file
            saved_catalog = Catalog()
            if os.path.exists(f'{picks_file}'):
                saved_catalog = read_events(picks_file)
            same_quake = None
            id = extractEventId(qmlevent)
            for q in saved_catalog:
                if extractEventId(q) == id:
                    same_quake = q
                    break
            if same_quake is not None:
                # quake is also in saved file, replace with current version of event
                saved_catalog.events.remove(same_quake)
            merge_picks_to_catalog(qmlevent, saved_catalog)
            saved_catalog.write(picks_file, format='QUAKEML')
            #saved_catalog.write("hypodd.pha", format='HYPODDPHA')

        seis = [] # force while to run
        sta = "dummy"
        quake = "dummy"
        if command == "next" or command == "next_quake":
            if command == "next_quake":
                # zip to end of station iterator so next() will go to next quake
                sta_itr.ending()
            net, sta, quake, seis = seis_itr.next()
            while len(seis) == 0 and sta is not None and quake is not None:
                print(f"No data for {net.code}_{sta.code} for event {quake.preferred_origin().time}...")
                net, sta, quake, seis = seis_itr.next()
        elif command == "prev" or command == "prev_quake":
            if command == "prev_quake":
                # zip to beginning of station iterator so prev() will go to previous quake
                sta_itr.beginning()
            net, sta, quake, seis = seis_itr.prev()
            while len(seis) == 0 and sta is not None and quake is not None:
                print(f"No data for {net.code}_{sta.code} for event {quake.preferred_origin().time}...")
                net, sta, quake, seis = seis_itr.prev()
        else:
            # quit
            return

        if len(seis) == 0:
            print(f"No more to do...")
            pickax.close()
        elif sta is not None and quake is not None:
            # set overall inventory if not already set
            if pickax.inventory is None:
                try:
                    pickax.inventory = seis_itr.station_itr.inv
                except AttributeError:
                    print("catch AttributeError")
                    pickax.inventory = None

            # check to see if any old saved quakes from same event

            if saved_catalog is None:
                saved_catalog = Catalog()
                if os.path.exists(f'{picks_file}'):
                    saved_catalog = read_events(picks_file)
            id = extractEventId(quake)
            for oldquake in saved_catalog:
                if extractEventId(oldquake) == id:
                    merge_picks_to_quake(oldquake, quake)

            all_chan = ",".join(list(map(lambda tr: tr.stats.channel, seis)))
            print(f"{len(seis)} {net.code}_{sta.code} {all_chan} {quake.preferred_origin().time}")
            inv = seis_itr.station_iterator().inv
            if inv is None:
                inv = Catalog(networks = [ net ])
            if inv is None:
                # keep the old inv?
                inv = pickax.inventory
            #preprocess(seis, inv)
            print("after preprocess")

            # could update both stream and Qml Event
            # pickax.update_data(st, catalog[0])
            # or just the stream if the event is the same
            pickax.update_data(seis, quake, inventory=inv)
        else:
            print(f"close as {sta is None} {quake is None}")
            pickax.close()
    return dosave
