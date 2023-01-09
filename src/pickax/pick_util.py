from obspy.clients.fdsn.header import URL_MAPPINGS
from obspy.clients.fdsn import Client

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
    if p.creation_info.agency_id is not None:
        author += p.creation_info.agency_id+" "
    if p.creation_info.author is not None:
        author += p.creation_info.author+ " "
    author = author.strip()
    offsetStr = f"({p.time-start} s)" if start is not None else ""
    return f"{pname} {p.time} {offsetStr} {amp_str} {author}{isArr}"

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

def pick_from_trace(pick, trace):
    return (pick.waveform_id.network_code == trace.stats.network and
            pick.waveform_id.station_code == trace.stats.station and
            pick.waveform_id.location_code == trace.stats.location and
            pick.waveform_id.channel_code == trace.stats.channel )

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
    @returns     Extracted Id, or None if we can't figure it out
    """
    eventId = qmlEvent.extra.eventid.value
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

    return None

def reloadQuakeMLWithPicks(qmlevent, host="USGS"):
    client = Client(host)
    eventid = extractEventId(qmlevent)
    if eventid is not None:
        cat = client.get_events(eventid=eventid)
        if len(cat) == 1:
            return cat[0]
        else:
            raise Error("more than one event returned, should not happen")
    return None
