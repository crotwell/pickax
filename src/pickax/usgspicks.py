import sys
import os
from pathlib import Path
import argparse
from obspy import read_events

from .pick_util import reloadQuakeMLWithPicks

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
        "--url",
        required=False,
        help="QuakeML URL to load",
    )
    parser.add_argument(
        "--dc",
        default="USGS",
        help="Remote FDSNWS host to reload events from, defaults to USGS",
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    if args.quakeml:
        if not os.path.exists(args.quakeml):
            print(f"File {args.quakeml} does not seem to exist, cowardly quitting...")
            return
        catalog_file = Path(args.quakeml)
        saved_file = catalog_file.parent / (args.quakeml+".save")
        catalog = read_events(catalog_file)
        for idx, qmlevent in enumerate(catalog):
            reloaded = reloadQuakeMLWithPicks(qmlevent, host=args.dc)
            catalog[idx] = reloaded
        os.rename(catalog_file, saved_file)
        catalog.write(catalog_file, format="QUAKEML")



if __name__ == "__main__":
    main()
