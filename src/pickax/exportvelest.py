
import re
import math
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog, read_inventory, Inventory
from .pick_util import (
    inventory_for_catalog_picks,
    arrival_for_pick,
    best_pick_at_station
)

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
def qml_to_phs_header(quake):
    mag = 0.0
    if quake.preferred_magnitude() is not None:
        mag = quake.preferred_magnitude().mag
    origin = quake.preferred_origin()
    otime = origin.time
    ymdhm = otime.strftime("%y%m%d %H%M")
    osec = otime.second+ (otime.microsecond/1000000)
    lat, latC = latToNS(origin.latitude)
    lon, lonC = lonToEW(origin.longitude)
    depth = origin.depth/1000
    if depth < 0.01:
        depth = 0.01 # velest never iterates if depth is 0
    return f"{ymdhm} {osec:5.2f} {lat:<7.4f}{latC} {lon:>8.4f}{lonC} {(depth):>7.2f}  {mag:5.2f}"

def pick_to_pha(pick, quake):
    weight = "1"
    wid = pick.waveform_id
    origin = quake.preferred_origin()
    pick_offset = pick.time-origin.time
    phase_hint = pick.phase_hint
    if phase_hint is None:
        a = arrival_for_pick(pick, quake)
        if a is not None and a.phase is not None:
            phase_hint = a.phase
        else:
            print(f"Warning: skipping pick as no phase_hint: {pick}")
    return f"  {wid.station_code:<6}  {phase_hint[0]}   {weight}   {pick_offset:5.2f}"

def format_velest(inv):
    lines = ["(a6,f7.4,a1,1x,f8.4,a1,1x,i4,1x,i1,1x,i3,1x,f5.2,2x,f5.2)"]
    idx = 259
    for n in inv:
        for s in n.stations:
            lat, latC = latToNS(s.latitude)
            lon, lonC = lonToEW(s.longitude)
            out = f"{s.code:<6}{lat:6.4f}{latC} {lon:8.4f}{lonC}    0 1 {idx:3d}  0.00   0.00"
            lines.append(out)
            idx += 3
    return lines

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Create VELEST input files."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "-q",
        "--quakeml",
        required=False,
        help="QuakeML file to load",
    )
    parser.add_argument(
        "-a",
        "--authors",
        nargs='*',
        required=False,
        default=[],
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
    parser.add_argument(
        "--failduplicate", help="fail if there are duplicate picks satisfying the criteria in the QuakeML file", action="store_true"
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    bad_file_chars_pat = re.compile(r'[\s:\(\)/]+')
    outdir = Path(".")
    if args.dir is not None:
        outdir = Path(args.dir)
        if not outdir.exists():
            outdir.mkdir(parents=True, exist_ok=True)
    if args.staxml:
        inv = read_inventory(args.staxml)
        lines = format_velest(inv)

        in_path = Path(args.staxml)
        outfile = Path(outdir / f"{in_path.stem}.sta")
        with open(outfile, "w") as f:
            for l in lines:
                f.write(f"{l}\n")
            f.write("\n")
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
        outfile = Path(outdir / f"{quakemlPath.stem}.pha")
        with open(outfile, "w") as phsfile:
            for idx, quake in enumerate(catalog):
                any_picks_at_all = False
                all_picks = quake.picks[:]
                all_picks = [pick for pick in all_picks if pick.phase_hint != "pick"]
                if not (args.authors is None or len(args.authors) == 0):
                    all_picks = [pick for pick in all_picks if \
                                 pick.creation_info.author in args.authors \
                                 or pick.creation_info.agency_id in args.authors]
                all_station_ids = set()
                for pick in all_picks:
                    staId = f"{pick.waveform_id.network_code}.{pick.waveform_id.station_code}"
                    all_station_ids.add(staId)
                out_picks = []
                for staId in all_station_ids:
                    p_pick = best_pick_at_station(all_picks, "P", staId, quake,
                                                  args.authors,
                                                  check_unique=args.failduplicate) # def inst code H,N
                    if p_pick is not None:
                        out_picks.append(p_pick)
                    s_pick = best_pick_at_station(all_picks, "S", staId,
                                                  quake, args.authors,
                                                  check_unique=args.failduplicate) # def inst code H,N
                    if s_pick is not None:
                        out_picks.append(s_pick)

                if len(out_picks) > 0:
                    phsfile.write(f"{qml_to_phs_header(quake)}\n")
                    for pick in out_picks:
                        phsfile.write(f"{pick_to_pha(pick, quake)}\n")
                    phsfile.write("\n")
                print(f"{len(out_picks)} picks used for {quake.preferred_origin().time}")
        if args.invws:
            inv = inventory_for_catalog_picks(catalog, args.authors)
            outfile = Path(outdir / f"pick_channels.staxml")
            inv.write(outfile, format="StationXML")
            lines = format_velest(inv)
            outfile = Path(outdir / f"pick_channels.sta")
            with open(outfile, "w") as f:
                for l in lines:
                    f.write(f"{l}\n")


    print("Done")


if __name__ == "__main__":
    main()
