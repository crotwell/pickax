
import re
import math
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog, read_inventory, Inventory
from .pick_util import inventory_for_catalog_picks, arrival_for_pick, station_for_pick
from .distaz import DistAz

def latToNS(lat):
    latC = "N"
    if lat < 0:
        latC = "S"
        lat = abs(lat)
    return lat, latC
def lonToEW(lon):
    lonC = "E"
    if lon < 0:
        lonC = "W"
        lon = abs(lon)
    return lon, lonC
def qml_to_phs_header(quake, index):
    mag = 0.0
    if quake.preferred_magnitude() is not None:
        mag = quake.preferred_magnitude().mag
    origin = quake.preferred_origin()
    otime = origin.time
    ymdhm = otime.strftime("%y%m%d %H%M")
    osec = otime.second+ (otime.microsecond/1000000)
    lat, latC = latToNS(origin.latitude)
    lon, lonC = lonToEW(origin.longitude)
    return f"{ymdhm} {osec:5.2f} {lat:<7.4f}{latC} {lon:>8.4f}{lonC} {(origin.depth/1000):>7.2f}  {mag:5.2f}"

def pick_to_distaz(pick, quake, inv):

    weight = "1"
    wid = pick.waveform_id
    sta = station_for_pick(pick, inv)
    if sta is None:
        return f"no station found for pick at {wid}"

    origin = quake.preferred_origin()
    distazcalc = DistAz(sta.latitude, sta.longitude, origin.latitude, origin.longitude)
    pick_offset = pick.time-origin.time
    phase_hint = pick.phase_hint
    if phase_hint is None:
        a = arrival_for_pick(pick, quake)
        if a is not None and a.phase is not None:
            phase_hint = a.phase
        else:
            print(f"Warning: skipping pick as no phase_hint: {pick}")
    return f"  {wid.station_code:<6}  {phase_hint[0]} {distazcalc.getDistanceKm()} km {distazcalc.getAz()} {distazcalc.getBaz()}"


def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Create Dist and azimuth for picks."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "-q",
        "--quakeml",
        required=True,
        help="QuakeML file to load",
    )
    parser.add_argument(
        "-a",
        "--authors",
        nargs='*',
        required=False,
        help="Authors of picks to pull from QuakeML file",
    )
    parser.add_argument(
        "-s",
        "--staxml",
        required=False,
        help="StationXML file to load",
    )
    parser.add_argument(
        "--invws",
        required=False,
        action="store_true",
        help="query StationXML from FDSN web service for all channels with picks",
    )
    parser.add_argument(
        "-d",
        "--dir",
        required=False,
        help="directory to save to",
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    bad_file_chars_pat = re.compile(r'[\s:\(\)/]+')
    outdir = Path(".")
    inv = None
    if args.dir is not None:
        outdir = Path(args.dir)
        if not outdir.exists():
            outdir.mkdir(parents=True, exist_ok=True)
    if args.staxml:
        inv = read_inventory(args.staxml)
    elif args.invws:
        inv = inventory_for_catalog_picks(catalog, args.authors)
    else:
        print("One of --invws or --staxml must be used")
        return

    if args.quakeml:
        quakemlPath = Path(args.quakeml)
        if quakemlPath.exists():
            catalog_file = Path(args.quakeml)
            saved_file = catalog_file.parent / (args.quakeml+".save")
        elif args.quakeml.startswith("http"):
            catalog_file = Path(Path(args.quakeml).name)
        else:
            print(f"File {args.quakeml} does not seem to exist, cowardly quitting...")
            return
        catalog = read_events(args.quakeml)
        outfile = Path(outdir / f"{quakemlPath.stem}.daz")
        with open(outfile, "w") as phsfile:
            for idx, quake in enumerate(catalog):
                any_picks_at_all = False
                pick_idx = 0
                for pick in quake.picks:
                    if pick.phase_hint == "pick":
                        continue
                    if args.authors is None or len(args.authors) == 0 \
                            or pick.creation_info.author in args.authors \
                            or pick.creation_info.agency_id in args.authors:
                        if not any_picks_at_all:
                            any_picks_at_all = True
                            phsfile.write(f"{qml_to_phs_header(quake, idx+1)}\n")
                        phsfile.write(f"{pick_to_distaz(pick, quake, inv)}\n")
                        pick_idx+=1
                if any_picks_at_all:
                    phsfile.write("\n")


    print("Done")


if __name__ == "__main__":
    main()
