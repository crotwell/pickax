from obspy.clients.fdsn.header import URL_MAPPINGS
from obspy.clients.fdsn import Client
from obspy.core.event.origin import Pick
from obspy.core.event.base import WaveformStreamID, CreationInfo
from obspy.core.event.resourceid import ResourceIdentifier
from obspy import UTCDateTime
from obspy.core.event.magnitude import Amplitude
import re

zap_space = re.compile(r'\s+')

def create_pick_on_stream(stream, time, phase="pick", creation_info=None, resource_prefix="pickax", filter_name=None):
    """
    Creates a pick based on a gui event, like keypress and mouse position.
    Optionally give the pick a phase name, defaults to "pick".
    """
    pick = Pick(resource_id=ResourceIdentifier(prefix=resource_prefix))
    pick.method_id = "PickAx"
    pick.phase_hint = phase
    pick.time = time
    pick.waveform_id = WaveformStreamID(network_code=stream[0].stats.network,
                                        station_code=stream[0].stats.station,
                                        location_code=stream[0].stats.location,
                                        channel_code=stream[0].stats.channel)
    if creation_info is not None:
        pick.creation_info = CreationInfo(
            agency_id=creation_info.agency_id,
            agency_uri=creation_info.agency_uri,
            author=creation_info.author,
            author_uri=creation_info.author_uri,
            creation_time=UTCDateTime(),
            version=creation_info.version
            )
    else:
        pick.creation_info = CreationInfo(
            author="PickAx",
            creation_time=UTCDateTime(),
            )
    amp = None
    for tr in stream:
        if tr.stats.starttime > time or tr.stats.endtime < time:
            continue
        # found trace that overlaps time
        offset = time - tr.stats.starttime
        index = round(offset/tr.stats.delta)
        if index >=0 and index < len(tr):
            amp = Amplitude(resource_id=ResourceIdentifier(prefix=resource_prefix))
            amp.generic_amplitude = tr.data[index]
            amp.pick_id = pick.resource_id
            amp.waveform_id = pick.waveform_id
            if filter_name is not None:
                filter_name = re.sub(zap_space, '_', filter_name)
                amp.filter_id = f"quakeml:pickax/filter/{filter_name}"
            amp.creation_info = pick.creation_info
            break
    return pick, amp

def pick_to_multiline(p, qmlevent=None, start=None):
    a = None
    amp = None
    if qmlevent is not None:
        a = arrival_for_pick(p, qmlevent)
        amp = amplitude_for_pick(p, qmlevent)

    amp_str = f"amp: {amp.generic_amplitude}" if amp is not None else ""
    pname = a.phase if a is not None and a.phase is not None else p.phase_hint
    isArr = ", Pick" if a is None else ", Arrival"
    author = ""
    if p.creation_info.agency_id is not None:
        author += p.creation_info.agency_id+" "
    if p.creation_info.author is not None:
        author += p.creation_info.author+ " "
    author = author.strip()
    ver = ""
    if p.creation_info.version is not None:
        ver = f" ({p.creation_info.version})"
    offsetStr = f"({p.time-start} s)" if start is not None else ""
    sourceId = f"{p.waveform_id.network_code}.{p.waveform_id.station_code}.{p.waveform_id.location_code}.{p.waveform_id.channel_code}"
    return [ pname, str(p.time), sourceId, f"{author}{ver}{isArr}" ]
def pick_to_string(p, qmlevent=None, start=None):
    a = None
    amp = None
    if qmlevent is not None:
        a = arrival_for_pick(p, qmlevent)
        amp = amplitude_for_pick(p, qmlevent)

    amp_str = f"amp: {amp.generic_amplitude}" if amp is not None else ""
    pname = a.phase if a is not None and a.phase is not None else p.phase_hint
    isArr = ", Pick" if a is None else ", Arrival"
    author = ""
    ver = ""
    if p.creation_info is not None:
        if p.creation_info.agency_id is not None:
            author += p.creation_info.agency_id+" "
        if p.creation_info.author is not None:
            author += p.creation_info.author+ " "
        if p.creation_info.version is not None:
            ver = f" ({p.creation_info.version})"
    author = author.strip()
    offsetStr = f"({p.time-start} s)" if start is not None else ""
    sourceId = f"{p.waveform_id.network_code}.{p.waveform_id.station_code}.{p.waveform_id.location_code}.{p.waveform_id.channel_code}"
    return f"{pname} {p.time} {sourceId} {offsetStr} {amp_str} {author}{ver}{isArr}"

def arrival_for_pick(pick, qmlevent):
    """
    Finds a matching arrival for the pick within the origins in the
    earthquake. If more than one match, the first is returned, if none
    then None is returned.
    """
    for o in qmlevent.origins:
        for a in o.arrivals:
            if pick.resource_id.id == a.pick_id.id:
                return a
    return None
def amplitude_for_pick( pick, qmlevent):
    """
    Finds a matching amplitude for the pick within the
    earthquake. If more than one match, the first is returned, if none
    then None is returned.
    """
    if pick.resource_id is None:
        return None
    for a in qmlevent.amplitudes:
        if a.pick_id is not None and pick.resource_id.id == a.pick_id.id:
            return a
    return None

def remove_pick(pick, qmlevent):
    for o in qmlevent.origins:
        for a in o.arrivals:
            if pick.resource_id.id == a.pick_id.id:
                o.arrivals.remove(a)
    amp = amplitude_for_pick(pick, qmlevent)
    if amp is not None:
        qmlevent.amplitudes.remove(amp)
    qmlevent.picks.remove(pick)
def pick_from_trace(pick, trace):
    return (pick.waveform_id.network_code == trace.stats.network and
            pick.waveform_id.station_code == trace.stats.station and
            pick.waveform_id.location_code == trace.stats.location and
            pick.waveform_id.channel_code == trace.stats.channel )

def same_author(creation_info_a, creation_info_b):
    if creation_info_a is None or creation_info_b is None:
        return False
    return creation_info_a.author == creation_info_b.author

def merge_picks_to_quake(qmlevent, out_qmlevent, author=None):
    """
    Merges picks from one quake to the other.
    """
    pick_list = qmlevent.picks
    if author is not None:
        pick_list = filter(lambda p: p.creation_info.agency_id == author or p.creation_info.author == author, pick_list)
    to_add = []
    for p in pick_list:
        found = False
        for catp in out_qmlevent.picks:
            if p.time == catp.time and \
                p.creation_info is not None and \
                catp.creation_info is not None and \
                p.creation_info.author == catp.creation_info.author:
                found = True
                break
        if not found:
            out_qmlevent.picks.append(p)
    for p in to_add:
        arr = arrival_for_pick(p, qmlevent)
        if arr is not None:
            # ?? what origin to add too
            out_qmlevent.preferred_origin().arrivals.append(arr)
        amp = amplitude_for_pick(p, qmlevent)
        if amp is not None:
            out_qmlevent.amplitudes.append(amp)

def merge_picks_to_catalog(qmlevent, catalog, author=None):
    id = extractEventId(qmlevent)
    pick_list = qmlevent.picks
    if author is not None:
        pick_list = filter(lambda p: p.creation_info.agency_id == author or p.creation_info.author == author, pick_list)
    found_quake = False
    for q in catalog:
        if extractEventId(q) == id:
            found_quake = True
            merge_picks_to_quake(qmlevent, q, author=author)
            break
    if not found_quake:
        clean_quake = qmlevent.copy()
        if author is not None:
            clean_quake.picks = list(filter(lambda p: p.creation_info.agency_id == author or p.creation_info.author == author, clean_quake.picks))
        catalog.append(clean_quake)
    return catalog


def UNKNOWN_PUBLIC_ID():
    length = 8
    letters = string.ascii_lowercase
    return "UNKNOWN_"+ ''.join(random.choice(letters) for i in range(length))

def extractEventId(qmlEvent, host=""):
    """
    Extracts the EventId from a QuakeML element, guessing from one of several
    incompatible (grumble grumble) formats.

    @param   qml Quake(Event) to extract from
    @param   host optional source of the xml to help determine the event id style
    @returns     Extracted Id, or resource_id.id if we can't figure it out
    """
    eventId = ""
    catalogEventSource = None
    if 'extra' in qmlEvent:
        if qmlEvent.extra.eventid is not None:
            eventId = qmlEvent.extra.eventid.value
        if qmlEvent.extra.eventsource is not None:
            catalogEventSource = qmlEvent.extra.eventsource.value

    if eventId != "":
        if host == "USGS" or catalogEventSource is not None:
            #USGS, NCEDC and SCEDC use concat of eventsource and eventId as eventit, sigh...
            return f"{catalogEventSource}{eventId}"
        else:
            return eventId

    publicid = qmlEvent.resource_id.id

    if publicid is not None:
      parsed = re.match(r'eventid=([\w\d]+)', publicid)
      if parsed:
        return parsed.group(1);

      parsed = re.match(r'evid=([\w\d]+)', publicid)
      if parsed:
        return parsed.group(1)

    return publicid

def reloadQuakeMLWithPicks(qmlevent, client=None, host="USGS", debug=False):
    if client is None:
        client = Client(host, _discover_services=False, debug=debug)
    eventid = extractEventId(qmlevent)
    if eventid is not None:
        cat = client.get_events(eventid=eventid)
        if len(cat) == 1:
            return cat[0]
        else:
            raise Error("more than one event returned, should not happen")
    return None

def inventory_for_catalog_picks(catalog, window=600, client=None, host="IRIS", debug=False):
    wid_list = []
    for qmlevent in catalog:
        otime = qmlevent.preferred_origin().time
        for pick in qmlevent.picks:
            wid = pick.waveform_id
            if wid.network_code is None or \
                wid.station_code is None or \
                wid.location_code is None or \
                wid.channel_code is None:
                print(f"None in Waveform_Id: {wid.network_code}, {wid.station_code}, {wid.location_code}, {wid.channel_code} for pick on {otime}")
            else:
                wid_list.append((wid.network_code, wid.station_code, wid.location_code, wid.channel_code, otime, (otime+600)))
    if client is None:
        client = Client(host, _discover_services=False, debug=debug)
    return client.get_stations_bulk(wid_list, level="channel", )

def station_for_pick(pick, inventory):
    wid = pick.waveform_id
    if wid.network_code is None or wid.station_code is None:
        return None
    for n in inventory.networks:
        if n.code == wid.network_code:
            for s in n.stations:
                if s.code == wid.station_code:
                    return s
    return None

DEF_INST_LIST = ["H", "N"]

def picks_by_author(pick_list, author):
    return [pick for pick in pick_list if \
                pick.creation_info.author == author \
                or pick.creation_info.agency_id == author]

def best_pick_at_station(pick_list, p_s, station_id, quake,
                         author_list=[],
                         inst_list=DEF_INST_LIST,
                         check_unique=False):
    all_picks = []
    for pick in pick_list:
        a = arrival_for_pick(pick, quake)
        pname = a.phase if a is not None and a.phase is not None else pick.phase_hint
        if pname == p_s:
            all_picks.append(pick)
    all_picks = [p for p in all_picks if \
                 station_id == f"{p.waveform_id.network_code}.{p.waveform_id.station_code}"]
    if len(author_list) != 0:
        for au in author_list:
            au_picks = picks_by_author(all_picks, au)
            if len(au_picks) > 0:
                pick = best_instrument_pick(au_picks,
                                            station_id,
                                            inst_list=DEF_INST_LIST,
                                            check_unique=check_unique)
                if pick is not None:
                    return pick
        # didn't find by author, so none?
        return None
    else:
        return best_instrument_pick(all_picks,
                                    station_id,
                                    inst_list=DEF_INST_LIST,
                                    check_unique=check_unique)

def best_instrument_pick(pick_list,
                         station_id,
                         inst_list=DEF_INST_LIST,
                         check_unique=False):
    """
    Finds pick on best (first in list) instrument code.
    """
    all_picks = [p for p in pick_list if \
         station_id == f"{p.waveform_id.network_code}.{p.waveform_id.station_code}"]
    for inst in inst_list:
        inst_picks = [pick for pick in all_picks if pick.waveform_id.channel_code[1] == inst]
        if len(inst_picks) == 0:
            pass
        elif check_unique and len(inst_picks)>1:
            raise Exception(f"More than one pick satisfies criteria for {station_id} on {inst}: {len(inst_picks)}")
        else:
            return inst_picks[0]
    if len(all_picks) == 0:
        return None
    elif check_unique and len(all_picks)>1:
        raise Exception(f"More than one pick satisfies criteria for {station_id}: {len(all_picks)}")
    else:
        return all_picks[0]
