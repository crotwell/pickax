from IPython import embed;
from IPython.core.getipython import get_ipython
from .pickax import PickAx
import obspy
from obspy.core.event.base import CreationInfo
import IPython
import sys
import os

from traitlets.config import Config

import argparse


def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Pickax, really simple seismic phase picker."
    )
    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )
    parser.add_argument(
        "-l",
        "--loader",
        required=False,
        help="Initialization loader script, run at startup",
    )
    parser.add_argument(
        "-s",
        "--seis",
        required=False,
        help="Seismogram file, loaded at startup",
    )
    return parser.parse_args()

def main():
    print("Hi PickAx!")
    args = do_parseargs()

    c = Config()
    c.InteractiveShellApp.exec_lines = [
        'import math',
        'from obspy.core.event.base import CreationInfo',
        'import obspy',
        'from pickax import PickAx',
        'import matplotlib.pyplot as plt',
        "plt.rcParams['toolbar'] = 'None'",
        "plt.rcParams['keymap.fullscreen'].remove('f')",
    ]
    if args.loader:
        if not os.path.exists(args.loader):
            print(f"File {args.loader} does not seem to exist, cowardly quitting...")
            return
        c.InteractiveShellApp.exec_lines.append(f"%run -i {args.loader}")
    elif args.seis:
        if not os.path.exists(args.seis):
            print(f"File {args.seis} does not seem to exist, cowardly quitting...")
            return
        c.InteractiveShellApp.exec_lines.append(f"st = obspy.read('{args.seis}')")
        c.InteractiveShellApp.exec_lines.append(f"pickax = PickAx(st)")
        c.InteractiveShellApp.exec_lines.append(f"pickax.draw()")
    c.InteractiveShell.colors = 'LightBG'
    c.InteractiveShell.confirm_exit = False
    c.TerminalIPythonApp.display_banner = False
    IPython.start_ipython(argv=[], config=c)


if __name__ == "__main__":
    main()
