
import re
import math
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog, read_inventory, Inventory



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
                codelon = "E" if c.longitude > 0 else "S"
                out = f"{s.code:<5} {n.code:<2}  {c.code:<3}  {deglat:>2} {minlat:>7.4f}{codelat}{deglon:>3} {minlon:>7.4f}{codelon}  {c.elevation:>5.1f}   A 0.00  0.00  0.00  0.00 3  0.00{c.location_code}{c.code}"
                print(out)
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
        "-s",
        "--staxml",
        required=False,
        help="StationXML file to load",
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
    if args.staxml:
        inv = read_inventory(args.staxml)
        lines = format_hypoinverse(inv)
        with open(f"{args.staxml}.sta", "w") as f:
            for l in lines:
                f.write(f"{l}\n")
    if args.quakeml:
        if os.path.exists(args.quakeml):
            catalog_file = Path(args.quakeml)
            saved_file = catalog_file.parent / (args.quakeml+".save")
        elif args.quakeml.startswith("http"):
            catalog_file = Path(Path(args.quakeml).name)
        else:
            print(f"File {args.quakeml} does not seem to exist, cowardly quitting...")
            return
        if args.dir is not None and not os.path.exists(args.dir):
            Path(args.dir).mkdir(parents=True, exist_ok=True)
        catalog = read_events(args.quakeml)
        for idx, qmlevent in enumerate(catalog):
            if args.dir is not None:
                dirPath = Path(args.dir)
                filename = origin_mag_to_string(qmlevent).strip()
                filename = re.sub(bad_file_chars_pat, '_', filename)
                filePath = Path(dirPath / filename)
                if not filePath.exists():
                    # only load picks if event file doesn't already exist
                    reloaded = reloadQuakeMLWithPicks(qmlevent, host=args.dc)
                    single_cat = Catalog([reloaded])
                    single_cat.write(filePath, format="QUAKEML")
                    if args.verbose:
                        print(f"Save {filePath}")
            else:
                reloaded = reloadQuakeMLWithPicks(qmlevent, host=args.dc)
                catalog[idx] = reloaded
        if args.dir is None:
            if saved_file is not None:
                os.rename(catalog_file, saved_file)
            catalog.write(catalog_file, format="QUAKEML")
    print("Done")


if __name__ == "__main__":
    main()
