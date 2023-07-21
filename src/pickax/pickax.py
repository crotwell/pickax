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

from .pickax_config import PickAxConfig, TRACE_AMP, GLOBAL_AMP, WINDOW_AMP
from .flag import PickFlag
from .seismograph import Seismograph
from .traveltime import TravelTimeCalc
from .pick_util import (
    pick_to_string,
    pick_from_trace,
    arrival_for_pick,
    amplitude_for_pick,
    pick_to_multiline,
    remove_pick,
    same_author
    )
from .help import print_help

class PickAx:
    """
    PickAx, a simple seismic picker, when you just need to dig a few
    arrivals out of the red clay.

    stream -- usually a waveform for a single channel
    qmlevent -- optional QuakeML Event to store picks in, created if not supplied
    config -- configuration object
    """
    def __init__(self,
                 stream=None,
                 qmlevent=None,
                 inventory =None,
                 config=None):
        self.config = config if config is not None else PickAxConfig()
        self.stream = stream if stream is not None else Stream()
        self.qmlevent = qmlevent
        self.inventory = inventory
        self.taveltime_calc = TravelTimeCalc(self.config.phase_list, self.config.model)
        self.display_groups = []
        self.seismographList = []
        self.start = None
        self.curr_filter = -1
        self._filtered_stream = None
        self.fig = plt.figure(figsize=self.config.figsize)
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
        sortedChannelCodes = sorted(list(uniq_chan_traces.keys()))
        for code in sortedChannelCodes:
            self.display_groups.append(uniq_chan_traces[code])

        self.start = self.calc_start()
        self.curr_filter = -1
        self._filtered_stream = None
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
        if self.config.finishFn is not None:
            self.config.finishFn(self.qmlevent, self.stream, command, self)
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
        title = self.config.titleFn(self.stream, self.qmlevent, self.inventory)
        if title is not None and len(title) > 0:
            self.fig.suptitle(title)
        position = 1
        for trList in self.display_groups:
            ax = self.fig.add_subplot(len(self.display_groups),1,position)
            position += 1
            sg = Seismograph(ax,
                            stream=trList,
                            config = self.config,
                            qmlevent = self.qmlevent,
                            inventory = self.inventory,
                            traveltime_calc = self.taveltime_calc,
                            )
            if self.config.amplitude_mode == TRACE_AMP:
                sg.unset_ylim()
            for pick in sg.channel_picks():
                is_mod = same_author(pick.creation_info, self.config.creation_info)
                arrival = arrival_for_pick(pick, self.qmlevent)
                pickFlag = self.create_pick_flag(pick, sg, is_modifiable=is_mod, arrival=arrival)
            self.seismographList.append(sg)
        if self.config.amplitude_mode == GLOBAL_AMP:
            gl_min, gl_max = self.calc_global_amp()
            for sg in self.seismographList:
                sg.set_ylim(gl_min, gl_max)
        for sg in self.seismographList:
            sg.draw()
        self.fig.tight_layout()
        self.fig.canvas.draw_idle()
        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
    def calc_global_amp(self):
        if (len(self.seismographList)) == 0:
            return (-1,1)
        gl_min, gl_max = self.seismographList[0].calc_amplitude_range()
        for sg in self.seismographList:
            sg_min, sg_max = sg.calc_zoom_amp()
            gl_min = min(gl_min, sg_min)
            gl_max = max(gl_max, sg_max)
        return (gl_min, gl_max)
    def close(self):
        """
        Close the window, goodnight moon.
        """
        plt.close()
    def on_key(self, event):
        """
        Event handler for key presses.
        """
        if event.key not in self.config.keymap:
            if event.key != "shift":
                print(f"unknown key function: {event.key}")
            return
        if self.config.keymap[event.key] != "ZOOM_IN":
            for sg in self.seismographList:
                sg.unset_zoom()

        if self.config.keymap[event.key] == "ZOOM_IN":
            for sg in self.seismographList:
                sg.do_zoom(event)
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] == "ZOOM_OUT":
            for sg in self.seismographList:
                sg.do_zoom_out()
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] == "ZOOM_ORIG":
            for sg in self.seismographList:
                sg.do_zoom_original()
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] =="CURR_MOUSE":
            if event.inaxes is None:
                return
            time, amp, offset = self.seismograph_for_axes(event.inaxes).mouse_time_amp(event)
            print(f"Time: {time} ({offset:.3f} s)  Amp: {amp}")
        elif self.config.keymap[event.key] =="EAST":
            if event.inaxes is None:
                if len(self.seismographList) > 0:
                    xmin, xmax, ymin, ymax = self.seismographList[0].ax.axis()
                else:
                    return
            else:
                xmin, xmax, ymin, ymax = event.inaxes.axis()
            xwidth = xmax - xmin
            xshift = xwidth/self.config.scroll_factor
            for sg in self.seismographList:
                sg.update_xlim(xmin-xshift, xmax-xshift)
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] =="WEST":
            if event.inaxes is None:
                if len(self.seismographList) > 0:
                    xmin, xmax, ymin, ymax = self.seismographList[0].ax.axis()
                else:
                    return
            else:
                xmin, xmax, ymin, ymax = event.inaxes.axis()
            xwidth = xmax - xmin
            xshift = xwidth/self.config.scroll_factor
            for sg in self.seismographList:
                sg.update_xlim(xmin+xshift, xmax+xshift)
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] == "AMP_MODE":
            self.config.toggle_amplitude_mode()
            if self.config.amplitude_mode == GLOBAL_AMP:
                gl_min, gl_max = self.calc_global_amp()
                for sg in self.seismographList:
                    sg.set_ylim(gl_min, gl_max)
            else:
                for sg in self.seismographList:
                    sg.unset_ylim()
            for sg in self.seismographList:
                sg.draw()
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key] =="GO_QUIT":
            self.do_finish("quit")
        elif self.config.keymap[event.key]  == "GO_NEXT":
            self.do_finish("next")
        elif self.config.keymap[event.key]  == "GO_PREV":
            self.do_finish("prev")
        elif self.config.keymap[event.key]  == "GO_NEXT_QUAKE":
            if self.config.seismogram_itr is not None:
                sta_itr = self.config.seismogram_itr.station_iterator()
                if sta_itr is not None:
                    sta_itr.ending()
            self.do_finish("next")
        elif self.config.keymap[event.key]  == "GO_PREV_QUAKE":
            if self.config.seismogram_itr is not None:
                sta_itr = self.config.seismogram_itr.station_iterator()
                if sta_itr is not None:
                    sta_itr.beginning()
                quake_itr = self.config.seismogram_itr.quake_iterator()
                if quake_itr is not None:
                    quake_itr.prev()
            self.do_finish("prev")
        elif self.config.keymap[event.key]  == "LIST_QUAKES":
            all = None
            if self.config.seismogram_itr is not None:
                quake_itr = self.config.seismogram_itr.quake_iterator()
                if quake_itr is not None:
                    all = quake_itr.all()
            if all is not None:
                for q in all:
                    o = q.preferred_origin()
                    m = q.preferred_magnitude()
                    mstr = "    "
                    if m is not None:
                        mstr = f"{m.mag}{m.magnitude_type}"
                    print(f"{o.time} {mstr} ({o.latitude}/{o.longitude})".strip())
            else:
                print("Iterator does not allow access to all quakes")

        elif self.config.keymap[event.key]  == "LIST_STATIONS":
            all = None
            if self.config.seismogram_itr is not None:
                sta_itr = self.config.seismogram_itr.station_iterator()
                if sta_itr is not None:
                    all = sta_itr.all_stations()
            if all is not None:
                for s in all:
                    print(f"{s.code} ({s.latitude}/{s.longitude})")
            else:
                print("Iterator does not allow access to all stations")

        elif self.config.keymap[event.key]  == "PICK_GENERIC":
            if event.inaxes is not None:
                self.do_pick(event)
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key]  == "PICK_P":
            if event.inaxes is not None:
                self.do_pick(event, phase="P")
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key]  == "PICK_S":
            if event.inaxes is not None:
                self.do_pick(event, phase="S")
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key]  == "DISPLAY_PICKS":
            print(self.display_picks(author=self.config.creation_info.author))
        elif self.config.keymap[event.key]  == "DISPLAY_ALL_PICKS":
            print(self.display_picks(include_station=True))
        elif self.config.keymap[event.key]  == "NEXT_FILTER":
            if self.curr_filter == len(self.config.filters)-1:
                self.curr_filter = -2
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter+1)
            self.curr_filter += 1
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key]  == "PREV_FILTER":
            if self.curr_filter < 0:
                self.curr_filter = len(self.config.filters)
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter-1)
            self.curr_filter -= 1
            self.fig.canvas.draw_idle()
        elif self.config.keymap[event.key]  == "HELP":
            print_help(self.config.keymap)
        elif self.config.keymap[event.key]  ==  "REMOVE_PICK":
            pass # handled in flag
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
            pick_list = filter(lambda p: p.creation_info is not None and (
                p.creation_info.agency_id == author \
                or p.creation_info.author == author), pick_list)
        return pick_list
    def create_pick_flag(self, pick, seismograph, is_modifiable, arrival=None):
        pickFlag = PickFlag(pick, seismograph, is_modifiable=is_modifiable, arrival=arrival)
        pickFlag.color_labelFn = self.config.pick_color_labelFn
        pickFlag.mouse_event_connect(self.fig.canvas)
        seismograph.flags.append(pickFlag)
        return pickFlag
    def do_pick(self, event, phase="pick"):
        sg = self.seismograph_for_axes(event.inaxes)
        pick = sg.do_pick(event, phase)
        pickFlag = self.create_pick_flag(pick, sg, is_modifiable=True)
        pickFlag.draw()
        return pick
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
