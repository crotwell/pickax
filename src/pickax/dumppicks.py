import argparse
from obspy import Catalog, read_events
import os
from pathlib import Path
from .pick_util import pick_to_string

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Dump Picks from QuakeML events in file."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "--from",
        required=True,
        dest='fromfiles',
        nargs='+',
        help="QuakeML files to load picks from",
    )
    parser.add_argument(
        "-a",
        "--author",
        help="only show picks from given author, defaults to all",
        default=None,
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    catalog = None
    catalog_file = None

    for qmlfile in args.fromfiles:
        print()
        print(qmlfile)
        print("---------------------------")
        in_catalog = read_events(Path(qmlfile))
        for in_quake in in_catalog:
            print(in_quake.short_str())
            for pick in in_quake.picks:
                if args.author is None \
                or pick.creation_info.author == args.author \
                or pick.creation_info.agency_id == args.author:
                    print(f"    {pick_to_string(pick, in_quake)}")

if __name__ == "__main__":
    main()
