from IPython import embed;
from IPython.core.getipython import get_ipython
from .pick_seismograms import PickSeis
import obspy
from obspy.core.event.base import CreationInfo
import IPython

from traitlets.config import Config


def main():
    print("Hi PickAxe!")

    c = Config()
    c.InteractiveShellApp.exec_lines = [
        'print("\\nimporting some things\\n")',
        'import math',
        'from obspy.core.event.base import CreationInfo',
        'import obspy',
        'from pickaxe import PickSeis',
    ]
    c.InteractiveShell.colors = 'LightBG'
    c.InteractiveShell.confirm_exit = False
    c.TerminalIPythonApp.display_banner = False
    IPython.start_ipython(argv=[], config=c)
    #embed()
