from .pick_util import merge_picks_to_catalog
import argparse
from obspy import Catalog, read_events
import os
from pathlib import Path

def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Merge Picks from QuakeML events from two files into one."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "--from",
        required=True,
        nargs='+',
        dest='fromfiles',
        help="QuakeML files to load picks from",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="QuakeML file to save picks to",
    )
    parser.add_argument(
        "-a",
        "--author",
        help="only copy picks from given author, defaults to all",
        default=None,
    )
    return parser.parse_args()

def main():
    args = do_parseargs()
    if args.to:
        catalog = None
        catalog_file = Path(args.to)
        saved_file = None
        if catalog_file.exists():
            catalog = read_events(catalog_file)
        else:
            print(f"File {args.to} does not seem to exist, create empty...")
            catalog = Catalog()

        for idx, qmlfile in enumerate(args.fromfiles):
            in_catalog = read_events(Path(qmlfile))
            for in_quake in in_catalog:
                merge_picks_to_catalog(in_quake, catalog, author=args.author)
        if catalog_file.exists():
            saved_file = catalog_file.parent / (args.to+".save")
            os.rename(catalog_file, saved_file)
        catalog.write(catalog_file, format="QUAKEML")



if __name__ == "__main__":
    main()
