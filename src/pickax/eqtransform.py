import csv
from obspy.clients.fdsn.header import URL_MAPPINGS
from obspy.clients.fdsn import Client
from obspy.core.event import Catalog, Event, read_events
from obspy.core.event.origin import Origin, Pick
from obspy.core.event.base import WaveformStreamID, CreationInfo
from obspy import UTCDateTime
from obspy.core.event.magnitude import Amplitude
from obspy.core.event.resourceid import ResourceIdentifier
import argparse
import os
from pathlib import Path

from .pick_util import merge_picks_to_quake


def read_eqt_csv(eqt_csv_file, lat=0, lon=0, depth=0):
    catalog = Catalog()
    cre_info = CreationInfo(author="EQTR",
                            create_time=UTCDateTime())
    with open(eqt_csv_file) as csv_fp:
        eqtreader = csv.DictReader(csv_fp)
        for row in eqtreader:
            dect_prop = row['detection_probability']
            wave_stream_id = WaveformStreamID(network_code=row['network'],
                                              station_code=row['station'],
                                              location_code='00',
                                              channel_code=f"{row['instrument_type']}Z")
            p = Pick(resource_id=ResourceIdentifier(prefix="sc.edu"),
                     time=UTCDateTime(row['p_arrival_time']),
                     phase_hint="P",
                     waveform_id=wave_stream_id,
                     creation_info=cre_info)
            s = Pick(resource_id=ResourceIdentifier(prefix="sc.edu"),
                     time=UTCDateTime(row['s_arrival_time']),
                     phase_hint='S',
                     waveform_id=wave_stream_id,
                     creation_info=cre_info)
            o = Origin(resource_id=ResourceIdentifier(prefix="sc.edu"),
                       time=UTCDateTime(row['event_start_time']),
                       latitude=lat,
                       longitude=lon,
                       depth=depth,
                       method_id=ResourceIdentifier(prefix="fake.eqtr.sc.edu"))
            e = Event(resource_id=ResourceIdentifier(prefix="sc.edu"),
                      origins=[o],
                      picks=[p,s])
            e.preferred_origin_id = o.resource_id
            catalog.append(e)
    return catalog


def do_parseargs():
    parser = argparse.ArgumentParser(
        description="EQTransform csv to QuakeML file."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "--csv",
        required=True,
        dest='fromcsv',
        help="EQTransform csv file to load picks from",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="QuakeML file to save picks to",
    )
    parser.add_argument(
        "--quakes",
        help="QuakeML file to find possible events",
    )
    parser.add_argument('--window',
        help="time window to match existing quakes",
        type=float,
        default=60)

    parser.add_argument('--latlon',
                        help="Set origin latitude/longitude",
                        nargs=2,
                        type=float,
                        default="0 0")
    parser.add_argument('--depth',
                        help="Set origin depth",
                        type=float,
                        default=0)
    return parser.parse_args()

def main():
    args = do_parseargs()
    lat = args.latlon[0]
    lon = args.latlon[1]
    csv_catalog = read_eqt_csv(args.fromcsv, lat=lat, lon=lon)
    quakes = Catalog()
    if args.quakes is not None:
        catalog = Catalog()
        quakes = read_events(args.quakes)
        for trq in csv_catalog:
            found = False
            for q in quakes:
                qtime = q.preferred_origin().time
                trqtime = trq.preferred_origin().time
                if abs(qtime - trqtime) < args.window:
                    merge_picks_to_quake(trq, q)
                    catalog.append(q)
                    found = True
                    break
            if not found:
                catalog.append(trq)
    else:
        catalog = csv_catalog


    if args.to:
        catalog_file = Path(args.to)
        if catalog_file.exists():
            saved_file = catalog_file.parent / (args.to+".save")
            os.rename(catalog_file, saved_file)
        catalog.write(catalog_file, format="QUAKEML")



if __name__ == "__main__":
    main()
