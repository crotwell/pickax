
import re
import math
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog, read_inventory, Inventory
from .pick_util import inventory_for_catalog_picks, arrival_for_pick

def qml_to_phs_header(quake):
    otime = quake.preferred_origin().time
    ymdhms = otime.strftime("%Y%m%d%H%M")
    osec = otime.second*100+ int(otime.microsecond/10000)
    lat = "34N 600" # 34. N, 6 min
    lon = " 80W1000" # -80 W 10 min
    depth ="  000"
    return f"{ymdhms}{osec:>5d}{lat}{lon}{depth}"

def pick_to_phs(pick, qmlevent):
    weight = "4"
    wid = pick.waveform_id
    sourceId = f"{wid.station_code:<5}{wid.network_code:<2}  {wid.channel_code:<3}"
    p_ymdhm = pick.time.strftime("%Y%m%d%H%M")
    psec = pick.time.second*100+ int(pick.time.microsecond/10000)
    pwave = f"   {weight}{p_ymdhm}    0   0  0"
    swave = f"    0   0  0"
    phase_hint = pick.phase_hint
    if phase_hint is None:
        a = arrival_for_pick(pick, qmlevent)
        if a is not None and a.phase is not None:
            phase_hint = a.phase
        else:
            print(f"Warning: skipping pick as no phase_hint: {pick}")
    if phase_hint == "P" or phase_hint.startswith("P"):
        pwave = f" P {weight}{p_ymdhm}{psec:>5d}   0"
    elif phase_hint == "S" or phase_hint.startswith("S"):
        swave = f"{psec:>5d} S {weight}"
    else:
        raise Exception(f"Unknown phase hint: {phase_hint}")
    otherstuff = "  18      0 0 40   0 -16  1215200  0     248  0  0   0  23J  "
    return f"{sourceId} {pwave}{swave}{otherstuff}{wid.location_code}"

def format_hypoinverse(inv):
    lines = []
    for n in inv:
        for s in n.stations:
            for c in s.channels:
                deglat = math.floor(abs(c.latitude))
                minlat = 60*(abs(c.latitude)-deglat)
                codelat = "N" if c.latitude > 0 else "S"
                deglon = math.floor(abs(c.longitude))
                minlon = 60*(abs(c.longitude)-deglon)
                codelon = "E" if c.longitude > 0 else "W"
                out = f"{s.code:<5} {n.code:<2}  {c.code:<3}  {deglat:>2} {minlat:>7.4f}{codelat}{deglon:>3} {minlon:>7.4f}{codelon}   00.0     0.00  0.00  0.00  0.00 0  1.00{c.location_code}{c.code}"
                lines.append(out)
    return lines

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Create Hypoinverse input files."
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
        lines = format_hypoinverse(inv)
        outfile = Path(outdir / f"{args.staxml}.sta")
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
                phsfile.write(f"{qml_to_phs_header(quake)}\n")
                #phsfile.write("SB4  BG  DPZ IPU1201001030833  826   1101    0   0   0      0 0  0  -9   0  1215205  0 54.0248  0  0  53   0J  -- 0DPZ X\n")
                #phsfile.write("SB4  BG  DPE    4201001030833    0   0  0  881ES 2  18      0 0 40   0 -16  1215200  0     248  0  0   0  23J  -- 0DPE\n")
                for pick in quake.picks:
                    if args.authors is None or len(args.authors) == 0 \
                            or pick.creation_info.author in args.authors \
                            or pick.creation_info.agency_id in args.authors:
                        phsfile.write(f"{pick_to_phs(pick, quake)}\n")
                phsfile.write(f"    9999\n")
        if args.invws:
            inv = inventory_for_catalog_picks(catalog, args.authors)
            outfile = Path(outdir / f"pick_channels.staxml")
            inv.write(outfile, format="StationXML")
            lines = format_hypoinverse(inv)
            outfile = Path(outdir / f"pick_channels.sta")
            with open(outfile, "w") as f:
                for l in lines:
                    f.write(f"{l}\n")


        #if args.hypodd:
        #    catalog.write(catalog_file, format="HYPODD")
    print("Done")


if __name__ == "__main__":
    main()
