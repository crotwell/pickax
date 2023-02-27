import re
import sys
import os
from pathlib import Path
import argparse
from obspy import read_events, Catalog

from .pick_util import reloadQuakeMLWithPicks
from .pickax_config import origin_mag_to_string

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="USGSPicks, reload QuakeML events from USGS to include picks and arrivals."
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
        "--dc",
        default="USGS",
        help="Remote FDSNWS host to reload events from, defaults to USGS",
    )
    parser.add_argument(
        "-d",
        "--dir",
        required=False,
        help="QuakeML directory, save one file per event",
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    bad_file_chars_pat = re.compile(r'[\s:\(\)/]+')
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



if __name__ == "__main__":
    main()
