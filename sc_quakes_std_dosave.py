import os
from obspy.clients.fdsn.header import FDSNNoDataException
from pickax import (
    PickAxConfig,
    FDSNQuakeIterator, FDSNStationIterator,
    FDSNSeismogramIterator,
    ThreeAtATime,
    CacheSeismogramIterator,
    merge_picks_to_catalog,
    merge_picks_to_quake,
    extractEventId,
    QuakeMLFileIterator,
    )
from obspy import Catalog, read_events

def create_dosaveFn(quake_query_params, station_query_params, seis_params, config=None, picks_file="picks_sc_quakes.qml"):
    if config is None:
        config = PickAxConfig()
    # Load stations, events and seismograms
    print(f"Load station metadata...")
    sta_itr = FDSNStationIterator(station_query_params, debug=config.debug)
    print(f"Networks: {len(sta_itr.inv.networks)}, Stations: {len(sta_itr)}")
    print(f"Load earthquakes...")
    if isinstance(quake_query_params, (str, os.PathLike)):
        # this loads from local file
        quake_itr = QuakeMLFileIterator(quake_query_params)
    else:
        # this loads quakes from remote server
        quake_itr = FDSNQuakeIterator(quake_query_params, debug=config.debug)
    print(f"Number of quakes: {len(quake_itr.quakes)}")

    # use ThreeAtATime to separate by band/inst code, ie seismometer then strong motion
    # at each station that has both
    seis_itr = ThreeAtATime(FDSNSeismogramIterator(quake_itr, sta_itr, debug=config.debug, **seis_params))
    # cache make prev/next a bit faster if data is already here
    seis_itr = CacheSeismogramIterator(seis_itr)

    # helper function, perhaps to preprocess the stream before picking
    def preprocess(stream, inv):
        if "preprocessed" not in stream[0].stats:
            stream.detrend()
            # deconvolution prefiltering, 10 sec to 45 Hz
            pre_filt = [0.02, 0.1, 45, 50]
            for tr in stream:
                tr.remove_response(inventory=inv, pre_filt=pre_filt, output="VEL", water_level=None)
                tr.stats["preprocessed"] = True

    # function called on quit, next or prev, allows saving of picks however you wish
    # here we save the quake as QuakeML, which will include the picks, and then
    # load the next seismogram if possible
    def dosave(qmlevent, stream, command, pickax):
        saved_catalog = None
        # set overall inventory if not already set
        if pickax.inventory is None:
            pickax.inventory = sta_itr.inv
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

        seis = [] # force while to run
        sta = "dummy"
        quake = "dummy"
        if command == "next":
            net, sta, quake, seis = seis_itr.next()
            while len(seis) == 0 and sta is not None and quake is not None:
                print(f"No data for {net.code}_{sta.code} for event {quake.preferred_origin().time}...")
                net, sta, quake, seis = seis_itr.next()
        elif command == "prev":
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
            preprocess(seis, sta_itr.inv)
            # could update both stream and Qml Event
            # pickax.update_data(st, catalog[0])
            # or just the stream if the event is the same
            pickax.update_data(seis, quake)
        else:
            print(f"close as {sta is None} {quake is None}")
            pickax.close()
    return dosave
