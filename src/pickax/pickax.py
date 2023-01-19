import sys
import os
import obspy
from obspy.taup import TauPyModel
import numpy
from obspy import read
from obspy.core import Stream
from IPython import get_ipython
import matplotlib.pyplot as plt
from prompt_toolkit.application.current import get_app

from .seismograph import Seismograph
from .traveltime import TravelTimeCalc
from .pick_util import pick_to_string, pick_from_trace, arrival_for_pick
from .help import print_help

# remember help.py if adding to keymap
DEFAULT_KEYMAP = {
    'c': "PICK_GENERIC",
    'a': "PICK_P",
    's': "PICK_S",
    'd': "DISPLAY_PICKS",
    'D': "DISPLAY_ALL_PICKS",
    'f': "NEXT_FILTER",
    'F': "PREV_FILTER",
    'x': "ZOOM_IN",
    'X': "ZOOM_OUT",
    'z': "ZOOM_ORIG",
    'w': "WEST",
    'e': "EAST",
    't': "CURR_MOUSE",
    'v': "GO_NEXT",
    'r': "GO_PREV",
    'q': "GO_QUIT",
    'h': "HELP",
}

class PickAx:
    """
    PickAx, a simple seismic picker, when you just need to dig a few
    arrivals out of the red clay.

    stream -- usually a waveform for a single channel
    qmlevent -- optional QuakeML Event to store picks in, created if not supplied
    finishFn -- a callback function for when the next (v) or prev (r) keys are pressed
    creation_info -- default creation info for the pick, primarily for author or agency_id
    filters -- list of filters, f cycles through these redrawing the waveform
    keymap -- optional dictionary of key to function
    """
    def __init__(self,
                 stream=None,
                 qmlevent=None,
                 inventory =None,
                 finishFn=None,
                 creation_info=None,
                 filters = [],
                 phase_list = [],
                 model = None,
                 figsize = (10,8),
                 keymap = {},
                 debug=False):
        if len(phase_list) > 0 and inventory is None:
            print("Warning: phase_list given but no inventory, unable to calculate travel times without a station location")
        self._init_keymap(keymap)
        self.debug = debug
        self.scroll_factor = 8

        self.stream = stream if stream is not None else Stream()
        self.qmlevent = qmlevent
        self.inventory = inventory
        self.finishFn = finishFn
        self.creation_info = creation_info
        self.filters = filters
        self.phase_list = phase_list
        self.model = model if model is not None else TauPyModel("ak135")
        self.taveltime_calc = TravelTimeCalc(self.phase_list, self.model)
        self.figsize = figsize
        self.display_groups = []
        self.seismographList = []
        self.start = None
        self.curr_filter = -1
        self._filtered_stream = None
        if creation_info is None and os.getlogin() is not None:
            self.creation_info = obspy.core.event.base.CreationInfo(
                author=os.getlogin()
                )
        self.fig = plt.figure(figsize=self.figsize)
        plt.get_current_fig_manager().set_window_title('Pickax')
        self.fig.canvas.mpl_connect('key_press_event', lambda evt: self.on_key(evt))
        self._prev_zoom_time = None
        if stream is None or len(stream) == 0:
            self.do_finish("next")
        else:
            self._init_data_(stream, qmlevent, inventory)
            self.draw()
    def _init_data_(self, stream, qmlevent=None, inventory=None):
        self.stream = stream
        if inventory is not None:
            # keep old inventory, often it is correct
            self.inventory = inventory
        if qmlevent is not None:
            self.qmlevent = qmlevent
        else:
            self.qmlevent = obspy.core.event.Event()
        self.display_groups = []
        self.seismographList = []
        uniq_chan_traces = {}
        for trace in stream:
            if trace.id not in uniq_chan_traces:
                uniq_chan_traces[trace.id] = Stream()
            uniq_chan_traces[trace.id].append(trace)
        sortedCodes = sorted(list(uniq_chan_traces.keys()))
        for code in sortedCodes:
            self.display_groups.append(uniq_chan_traces[code])

        self.start = self.calc_start()
        self.curr_filter = -1
        self._filtered_stream = None
    def _init_keymap(self, keymap):
        self.keymap = {}
        for k,v in DEFAULT_KEYMAP.items():
            self.keymap[k] = v
        for k,v in keymap.items():
            self.keymap[k] = v
    def update_data(self, stream, qmlevent=None, inventory=None):
        """
        Updates waveform and optionally earthquake and redraws.
        """
        if qmlevent is None:
            # reuse current event
            qmlevent = self.qmlevent
        self._init_data_(stream, qmlevent, inventory)
        self.draw()
    def do_finish(self, command):
        """
        Runs the supplied finish function with earthquake, stream and the
        next command. Command will be one of quit, next, prev. Generally
        the finish function is responsible for calling update_data with
        the next or previous seismogram.
        """
        if self.finishFn is not None:
            self.finishFn(self.qmlevent, self.stream, command, self)
        else:
            print(self.display_picks())
            self.close()
            if command == "quit":
                print("Goodbye.")
                #ip = get_ipython()
                #ip.ask_exit()
                #get_app().exit(exception=EOFError)
    def clear(self):
        self.fig.clear()
        self.seismographList = []
        self.fig.canvas.draw_idle()
    def draw(self):
        self.clear()
        position = 1
        for trList in self.display_groups:
            ax = self.fig.add_subplot(len(self.display_groups),1,position)
            position += 1
            sg = Seismograph(ax, trList,
                            qmlevent = self.qmlevent,
                            inventory = self.inventory,
                            finishFn = self.finishFn,
                            creation_info = self.creation_info,
                            filters = self.filters,
                            keymap = self.keymap,
                            traveltime_calc = self.taveltime_calc,
                            )
            sg.draw()
            self.seismographList.append(sg)
        self.fig.tight_layout()
        self.fig.canvas.draw_idle()
        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
    def close(self):
        """
        Close the window, goodnight moon.
        """
        plt.close()
    def on_key(self, event):
        """
        Event handler for key presses.
        """
        if event.key not in self.keymap:
            if event.key != "shift":
                print(f"unknown key function: {event.key}")
            return
        if self.keymap[event.key] != "ZOOM_IN":
            for sg in self.seismographList:
                sg.unset_zoom()

        if self.keymap[event.key] == "ZOOM_IN":
            for sg in self.seismographList:
                sg.do_zoom(event)
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] == "ZOOM_OUT":
            for sg in self.seismographList:
                sg.do_zoom_out()
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] == "ZOOM_ORIG":
            for sg in self.seismographList:
                sg.do_zoom_original()
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] =="CURR_MOUSE":
            time, amp, offset = self.seismograph_for_axes(event.inaxes).mouse_time_amp(event)
            print(f"Time: {time} ({offset:.3f} s)  Amp: {amp}")
        elif self.keymap[event.key] =="EAST":
            xmin, xmax, ymin, ymax = event.inaxes.axis()
            xwidth = xmax - xmin
            xshift = xwidth/self.scroll_factor
            for sg in self.seismographList:
                sg.update_xlim(xmin-xshift, xmax-xshift)
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] =="WEST":
            xmin, xmax, ymin, ymax = event.inaxes.axis()
            xwidth = xmax - xmin
            xshift = xwidth/self.scroll_factor
            for sg in self.seismographList:
                sg.update_xlim(xmin+xshift, xmax+xshift)
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] =="GO_QUIT":
            self.do_finish("quit")
        elif self.keymap[event.key]  == "GO_NEXT":
            self.do_finish("next")
        elif self.keymap[event.key]  == "GO_PREV":
            self.do_finish("prev")
        elif self.keymap[event.key]  == "PICK_GENERIC":
            if event.inaxes is not None:
                self.do_pick(event)
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key]  == "PICK_P":
            if event.inaxes is not None:
                self.do_pick(event, phase="P")
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key]  == "PICK_S":
            if event.inaxes is not None:
                self.do_pick(event, phase="S")
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key]  == "DISPLAY_PICKS":
            print(self.display_picks(author=self.creation_info.author))
        elif self.keymap[event.key]  == "DISPLAY_ALL_PICKS":
            print(self.display_picks(include_station=True))
        elif self.keymap[event.key]  == "NEXT_FILTER":
            if self.curr_filter == len(self.filters)-1:
                self.curr_filter = -2
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter+1)
            self.curr_filter += 1
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key]  == "PREV_FILTER":
            if self.curr_filter < 0:
                self.curr_filter = len(self.filters)
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter-1)
            self.curr_filter -= 1
            print(self.curr_filter)
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key]  == "HELP":
            print_help(self.keymap)
        else:
            print(f"Oops, key={event.key}")

    def get_picks(self, include_station=False, author=None):
        pick_list = []
        for sg in self.seismographList:
            if include_station:
                for p in sg.station_picks():
                    if p not in pick_list:
                        pick_list.append(p)
            else:
                for p in sg.channel_picks():
                    if p not in pick_list:
                        pick_list.append(p)
        if author is not None:
            pick_list = filter(lambda p: p.creation_info.agency_id == author or p.creation_info.author == author, pick_list)
        return pick_list

    def do_pick(self, event, phase="pick"):
        return self.seismograph_for_axes(event.inaxes).do_pick(event, phase)
    def seismograph_for_axes(self, ax):
        for sg in self.seismographList:
            if sg.ax == ax:
                return sg
        return None

    def list_channels(self):
        """
        Lists the channel codes for all traces in the stream, removing duplicates.
        Usually all traces will be from a single channel.
        """
        chans = []
        for tr in self.stream:
            stats = tr.stats
            nslc = f"{stats.network}_{stats.station}_{stats.location}_{stats.channel}"
            if nslc not in chans:
                chans.append(nslc)
        return chans
    def display_picks(self, include_station=False, author=None):
        """
        Creates a string showing the current channels, earthquake and all the
        picks on the current stream.
        """
        quakes = []
        for sg in self.seismographList:
            if not sg.qmlevent in quakes:
                quakes.append(sg.qmlevent)
        lines = []
        lines += self.list_channels()
        lines.append("")
        for q in quakes:
            lines.append(q.short_str())
        lines.append("")
        for p in self.get_picks(include_station=include_station, author=author):
            lines.append(pick_to_string(p, qmlevent=self.qmlevent))
        return "\n".join(lines)
    def calc_start(self):
        return min([trace.stats.starttime for trace in self.stream])
