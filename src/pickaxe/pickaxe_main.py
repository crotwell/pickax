from IPython import embed;
from IPython.core.getipython import get_ipython
from .pickaxe import PickAxe
import obspy
from obspy.core.event.base import CreationInfo
import IPython
import sys

from traitlets.config import Config

import argparse


def do_parseargs():
    parser = argparse.ArgumentParser(
        description="Pickaxe, really simple seismic phase picker."
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
    print("Hi PickAxe!")
    args = do_parseargs()

    c = Config()
    c.InteractiveShellApp.exec_lines = [
        'import math',
        'from obspy.core.event.base import CreationInfo',
        'import obspy',
        'from pickaxe import PickAxe',
        'import matplotlib.pyplot as plt',
        "plt.rcParams['toolbar'] = 'None'",
        "plt.rcParams['keymap.fullscreen'].remove('f')",
    ]
    if args.loader:
        c.InteractiveShellApp.exec_lines.append(f"%run -i {args.loader}")
    elif args.seis:
        c.InteractiveShellApp.exec_lines.append(f"st = obspy.read('{args.seis}')")
        c.InteractiveShellApp.exec_lines.append(f"pickaxe = PickAxe(st)")
        c.InteractiveShellApp.exec_lines.append(f"pickaxe.draw()")
    c.InteractiveShell.colors = 'LightBG'
    c.InteractiveShell.confirm_exit = False
    c.TerminalIPythonApp.display_banner = False
    IPython.start_ipython(argv=[], config=c)


if __name__ == "__main__":
    main()
