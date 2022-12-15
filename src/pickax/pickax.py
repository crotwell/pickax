import sys
import os
import obspy
import numpy
from obspy import read
from IPython import get_ipython
import matplotlib.pyplot as plt
from prompt_toolkit.application.current import get_app

from .blit_manager import BlitManager
from .seismograph import Seismograph
from .pick_util import pick_to_string, pick_from_trace, arrival_for_pick


DEFAULT_KEYMAP = {
    'c': "PICK_GENERIC",
    'a': "PICK_P",
    's': "PICK_S",
    'd': "DISPLAY_PICKS",
    'D': "DISPLAY_ALL_PICKS",
    'f': "NEXT_FILTER",
    'F': "PREV_FILTER",
    'v': "GO_NEXT",
    'r': "GO_PREV",
    'q': "GO_QUIT",
    'x': "ZOOM_IN",
    'X': "ZOOM_OUT",
    'w': "WEST",
    'e': "EAST",
    't': "CURR_MOUSE",
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
                 stream,
                 qmlevent=None,
                 finishFn=None,
                 creation_info=None,
                 filters = [],
                 figsize = (10,8),
                 keymap = {}):
        self._init_keymap(keymap)
        self.display_groups = []
        self.seismographList = []
        uniq_chan_traces = {}
        for trace in stream:
            if trace.id not in uniq_chan_traces:
                uniq_chan_traces[trace.id] = []
            uniq_chan_traces[trace.id].append(trace)
        sortedCodes = sorted(list(uniq_chan_traces.keys()))
        for code in sortedCodes:
            self.display_groups.append(uniq_chan_traces[code])


        self.finishFn = finishFn
        self.creation_info = creation_info
        self.filters = filters
        self.figsize = figsize
        self._init_data_(stream, qmlevent)
        if creation_info is None and os.getlogin() is not None:
            self.creation_info = obspy.core.event.base.CreationInfo(
                author=os.getlogin()
                )
        self.fig = plt.figure(figsize=self.figsize)
        self.fig.canvas.mpl_connect('key_press_event', lambda evt: self.on_key(evt))
        self.bm = BlitManager(self.fig.canvas, [])
        self._prev_zoom_time = None
    def _init_data_(self, stream, qmlevent=None):
        self.stream = stream
        if qmlevent is not None:
            self.qmlevent = qmlevent
        else:
            self.qmlevent = obspy.core.event.Event()
        self.start = self.calc_start()
        self.curr_filter = -1
        self._filtered_stream = None
    def _init_keymap(self, keymap):
        self.keymap = {}
        for k,v in DEFAULT_KEYMAP.items():
            self.keymap[k] = v
        for k,v in keymap.items():
            self.keymap[k] = v
    def update_data(self, stream, qmlevent=None):
        """
        Updates waveform and optionally earthquake and redraws.
        """
        if qmlevent is not None:
            self._init_data_(stream, qmlevent)
        else:
            # reuse current event
            self._init_data_(stream, self.qmlevent)
        self.clear_trace()
        self.clear_flags()
        self.ax.clear()
        self.ax.set_title(f"Pickax {' '.join(self.list_channels())}")
        self.draw()
    def __saved_update_draw(self):
        self.draw_stream()
        for pick in self.channel_picks():
            self.draw_flag(pick, arrival_for_pick(pick, self.qmlevent))
        self.ax.set_ylabel("")

        self.ax.relim()
        self.fig.canvas.draw_idle()
    def do_finish(self, command):
        """
        Runs the supplied finish function with earthquake, stream and the
        next command. Command will be one of quit, next, prev. Generally
        the finish function is responsible for calling update_data with
        the next or previous seismogram.
        """
        if self.finishFn is not None:
            self.finishFn(self.qmlevent, self.stream, command)
        else:
            print(self.display_picks())
            self.close()
            if command == "quit":
                print("Goodbye.")
                #ip = get_ipython()
                #ip.ask_exit()
                #get_app().exit(exception=EOFError)
    def draw(self):
        position = 1
        for trList in self.display_groups:
            ax = self.fig.add_subplot(len(self.display_groups),1,position)
            position += 1
            sg = Seismograph(ax, trList,
                            qmlevent = self.qmlevent,
                            finishFn = self.finishFn,
                            creation_info = self.creation_info,
                            filters = self.filters,
                            keymap = self.keymap,
                            bm = self.bm)
            sg.draw()
            self.seismographList.append(sg)
        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
    def clear_trace(self):
        """
        Clears the waveforms from the display.
        """
        for artist in self.bm._trace_artists:
            artist.remove()
            self.bm._artists.remove(artist)
        self.bm._trace_artists = []
    def clear_flags(self):
        """
        Clears pick flags from the display.
        """
        for artist in self.bm._flag_artists:
            artist.remove()
            self.bm._artists.remove(artist)
        self.bm._flag_artists = []
        # also clear x zoom marker if present
        self.bm.unset_zoom_bound()
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
            self._prev_zoom_time = None
            self.bm.unset_zoom_bound()
        else:
            # event.key=="x":
            if self._prev_zoom_time is not None:
                self.bm.unset_zoom_bound()
                if event.xdata > self._prev_zoom_time:
                    self.ax.set_xlim(left=self._prev_zoom_time, right=event.xdata)
                else:
                    self.ax.set_xlim(left=event.xdata, right=self._prev_zoom_time)
                self.zoom_amp()
                self.fig.canvas.draw_idle()
                self._prev_zoom_time = None
            else:
                self._prev_zoom_time = event.xdata
                xmin, xmax, ymin, ymax = self.ax.axis()
                mean = (ymin+ymax)/2
                hw = 0.9*(ymax-ymin)/2
                x = [event.xdata, event.xdata]
                y = [mean-hw, mean+hw]
                color = "black"
                (ln,) = self.ax.plot(x,y,color=color, lw=1, animated=True)
                self.bm.set_zoom_bound(ln)
                self.bm.update()

        if self.keymap[event.key] == "ZOOM_OUT":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin-xwidth/2, xmax+xwidth/2)
            self.zoom_amp()
            self.bm.unset_zoom_bound()

            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] =="CURR_MOUSE":
            offset = event.xdata
            time = self.start + offset
            amp = event.ydata
            print(f"Time: {time} ({offset} s)  Amp: {amp}")
        elif self.keymap[event.key] =="EAST":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin+xwidth/2, xmax+xwidth/2)
            self.zoom_amp()
            self.fig.canvas.draw_idle()
        elif self.keymap[event.key] =="WEST":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin-xwidth/2, xmax-xwidth/2)
            self.zoom_amp()
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
        elif self.keymap[event.key]  == "PICK_P":
            if event.inaxes is not None:
                self.do_pick(event, phase="P")
        elif self.keymap[event.key]  == "PICK_S":
            if event.inaxes is not None:
                self.do_pick(event, phase="S")
        elif self.keymap[event.key]  == "DISPLAY_PICKS":
            print(self.seismograph_for_axes(event.inaxes).display_picks(author=self.creation_info.author))
        elif self.keymap[event.key]  == "DISPLAY_ALL_PICKS":
            print(self.display_picks(include_station=True))
        elif self.keymap[event.key]  == "NEXT_FILTER":
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter+1)
        elif self.keymap[event.key]  == "PREV_FILTER":
            if self.curr_filter < 0:
                self.curr_filter = len(self.filters)
            for sg in self.seismographList:
                sg.do_filter(self.curr_filter-1)

    def get_picks(self, include_station, author):
        pick_list = []
        for sg in self.seismographList:
            if include_station:
                pick_list += sg.station_picks()
            else:
                pick_list += sg.channel_picks()
        if author is not None:
            pick_list = filter(lambda p: p.creation_info.agency_id == author or p.creation_info.author == author, pick_list)
        return pick_list

    def do_pick(self, event, phase=None):
        return self.seismograph_for_axes(event.inaxes).do_pick(event, phase)
    def seismograph_for_axes(self, ax):
        for sg in self.seismographList:
            if sg.ax == ax:
                print("found Seismograph for event ")
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
            print("sg")
            lines.append(q.short_str())
        lines.append("")
        for q in quakes:
            for tr in self.stream:
                net_code = tr.stats.network
                sta_code = tr.stats.station
                all_picks = filter(lambda p: pick_from_trace(p, tr), q.picks)
                for p in all_picks:
                    lines.append(pick_to_string(p, qmlevent=q))
        return "\n".join(lines)
    def calc_start(self):
        return min([trace.stats.starttime for trace in self.stream])
