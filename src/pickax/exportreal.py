
import re
import math
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog, read_inventory, Inventory
from .pick_util import inventory_for_catalog_picks, arrival_for_pick

def qml_to_phs_header(quake, index):
    origin = quake.preferred_origin()
    otime = origin.time
    ymdhm = otime.strftime("%Y %m %d %H %M")
    osec = otime.second*100+ int(otime.microsecond/10000)
    return f"# {ymdhm} {osec:7.3f} {origin.latitude} {origin.longitude} {origin.depth/1000} 2 0 0 {index}"

def pick_to_phs(pick, quake):
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
    return f"{wid.station_code} {pick_offset:8.4f} {weight} {phase_hint[0]}"

def format_real(inv):
    lines = []
    for n in inv:
        for s in n.stations:
            for c in s.channels:
                elev_km = c.elevation/1000
                out = f"{c.latitude} {c.longitude} {n.code} {s.code} {c.code} {elev_km:7.3f}"
                lines.append(out)
    return lines

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Create REAL input files."
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
    if args.dir is not None:
        outdir = Path(args.dir)
        if not outdir.exists():
            outdir.mkdir(parents=True, exist_ok=True)
    if args.staxml:
        inv = read_inventory(args.staxml)
        lines = format_real(inv)

        in_path = Path(args.staxml)
        outfile = Path(outdir / f"{in_path.stem}.sta")
        with open(outfile, "w") as f:
            for l in lines:
                f.write(f"{l}\n")
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
        outfile = Path(outdir / f"{quakemlPath.stem}.phs")
        with open(outfile, "w") as phsfile:
            for idx, quake in enumerate(catalog):
                phsfile.write(f"{qml_to_phs_header(quake, idx+1)}\n")
                for pick in quake.picks:
                    if pick.phase_hint == "pick":
                        continue
                    if args.authors is None or len(args.authors) == 0 \
                            or pick.creation_info.author in args.authors \
                            or pick.creation_info.agency_id in args.authors:
                        phsfile.write(f"{pick_to_phs(pick, quake)}\n")
        if args.invws:
            inv = inventory_for_catalog_picks(catalog, args.authors)
            outfile = Path(outdir / f"pick_channels.staxml")
            inv.write(outfile, format="StationXML")
            lines = format_real(inv)
            outfile = Path(outdir / f"pick_channels.sta")
            with open(outfile, "w") as f:
                for l in lines:
                    f.write(f"{l}\n")


    print("Done")


if __name__ == "__main__":
    main()
