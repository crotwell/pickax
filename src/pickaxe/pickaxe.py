import sys
import os
import obspy
from obspy import read
import matplotlib.pyplot as plt
from .blit_manager import BlitManager


class PickAxe:
    """
    PickAxe, a simple seismic picker, when you just need to dig a few
    arrivals out of the red clay.

    stream -- usually a waveform for a single channel
    qmlevent -- optional QuakeML Event to store picks in, created if not supplied
    finishFn -- a callback function for when the next (v) or prev (r) keys are pressed
    creation_info -- default creation info for the pick, primarily for author or agency_id
    filters -- list of filters, f cycles through these redrawing the waveform
    """
    def __init__(self,
                 stream,
                 qmlevent=None,
                 finishFn=None,
                 creation_info=None,
                 filters = []):
        self.finishFn = finishFn
        self.creation_info = creation_info
        self.filters = filters
        self._init_data_(stream, qmlevent)
        if creation_info is None and os.getlogin() is not None:
            self.creation_info = obspy.core.event.base.CreationInfo(
                author=os.getlogin()
                )
        self.fig, self.ax = plt.subplots()
#        self.fig.canvas.mpl_connect('button_press_event', lambda evt: self.onclick(evt))
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
    def update_data(self, stream, qmlevent=None):
        """
        Updates waveform and optionally earthquake and redraws.
        """
        self._init_data_(stream, qmlevent)
        self.clear_trace()
        self.clear_flags()
        self.ax.clear()
        self.ax.set_title(f"Pickaxe {self.list_channels()}")
        self.draw()
    def __saved_update_draw(self):
        self.draw_stream()
        for pick in self.channel_picks():
            self.draw_flag(pick, self.arrival_for_pick(pick))
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
                sys.exit(0)
    def draw(self):
        self.ax.set_xlabel(f'seconds from {self.start}')
        stats = self.stream[0].stats
        self.ax.set_title(f"Pickaxe {self.list_channels()}")
        # add lines
        self.draw_stream()
        for pick in self.channel_picks():
            self.draw_flag(pick, self.arrival_for_pick(pick))
        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
    def draw_stream(self):
        draw_stream = self._filtered_stream if self._filtered_stream is not None else self.stream
        for trace in draw_stream:
            (ln,) = self.ax.plot(trace.times(),trace.data,color="black", lw=0.5, animated=True)
            self.bm.add_trace_artist(ln)

    def arrival_for_pick(self, pick):
        """
        Finds a matching arrival for the pick within the origins in the
        earthquake. If more than one match, the first is returned, if none
        then None is returned.
        """
        for o in self.qmlevent.origins:
            for a in o.arrivals:
                if pick.resource_id.id == a.pick_id.id:
                    return a
        return None
    def station_picks(self):
        """
        Finds all picks in the earthquake whose waveform_id matches the
        streams network and station codes.
        """
        sta_code = self.stream[0].stats.station
        net_code = self.stream[0].stats.network
        return filter(lambda p: p.waveform_id.network_code == net_code and p.waveform_id.station_code == sta_code, self.qmlevent.picks)
    def channel_picks(self):
        """
        Finds all picks in the earthquake whose waveform_id matches the
        streams network, station, location and channel codes.
        """
        loc_code = self.stream[0].stats.location
        chan_code = self.stream[0].stats.channel
        sta_picks = self.station_picks()
        return filter(lambda p: p.waveform_id.location_code == loc_code and p.waveform_id.channel_code == chan_code, sta_picks)

    def draw_flag(self, pick, arrival=None):
        """
        Draws flages for each pick.
        """
        at_time = pick.time - self.start
        xmin, xmax, ymin, ymax = self.ax.axis()
        mean = (ymin+ymax)/2
        hw = 0.9*(ymax-ymin)/2
        x = [at_time, at_time]
        y = [mean-hw, mean+hw]
        color = "red"
        if arrival is not None:
            color = "blue"
        (ln,) = self.ax.plot(x,y,color=color, lw=1, animated=True)
        label = None
        label_str = "pick"
        if arrival is not None:
            label_str = arrival.phase
        elif pick.phase_hint is not None:
            label_str = pick.phase_hint
        label = self.ax.annotate(label_str, xy=(x[1], mean+hw*0.9), xytext=(x[1], mean+hw*0.9),  color=color, animated=True)
        self.bm.add_flag_artist(ln)
        self.bm.add_flag_artist(label)
    def do_pick(self, event, phase="pick"):
        """
        Creates a pick based on a gui event, like keypress and mouse position.
        Optionally give the pick a phase name, defaults to "pick".
        """
        p = obspy.core.event.origin.Pick()
        p.phase_hint = phase
        p.time = self.start + event.xdata
        p.waveform_id = obspy.core.event.base.WaveformStreamID(network_code=self.stream[0].stats.network,
                                                               station_code=self.stream[0].stats.station,
                                                               location_code=self.stream[0].stats.location,
                                                               channel_code=self.stream[0].stats.channel)
        if self.creation_info is not None:
            p.creation_info = obspy.core.event.base.CreationInfo(
                agency_id=self.creation_info.agency_id,
                agency_uri=self.creation_info.agency_uri,
                author=self.creation_info.author,
                author_uri=self.creation_info.author_uri,
                creation_time=obspy.UTCDateTime(),
                )
        self.qmlevent.picks.append(p)
        self.draw_flag(p)
        self.bm.update()
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
    def do_filter(self, idx):
        """
        Applies the idx-th filter to the waveform and redraws.
        """
        self.clear_trace()
        if idx < 0 or idx >= len(self.filters):
            self._filtered_stream = self.stream
            self.curr_filter = -1
        else:
            filterFn = self.filters[idx]['fn']
            orig_copy = self.stream.copy()
            out_stream = filterFn(orig_copy, self._filtered_stream, self.filters[idx]['name'], idx )
            if out_stream is not None:
                # fun returned new stream
                self._filtered_stream = out_stream
            else:
                # assume filtering done in place
                self._filtered_stream = orig_copy
            self.curr_filter = idx
        self.draw_stream()
        if self.curr_filter != -1:
            self.ax.set_ylabel(self.filters[idx]['name'])
        else:
            self.ax.set_ylabel("")

        self.ax.relim()
        self.fig.canvas.draw_idle()
    def close(self):
        """
        Close the window, goodnight moon.
        """
        plt.close()
    def on_key(self, event):
        """
        Event handler for key presses.
        """
        if event.key!="x":
            self._prev_zoom_time = None
        else:
            # event.key=="x":
            if self._prev_zoom_time is not None:
                self.ax.set_xlim(self._prev_zoom_time, event.xdata)
                self.fig.canvas.draw_idle()
                self._prev_zoom_time = None
            else:
                self._prev_zoom_time = event.xdata

        if event.key=="X":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin-xwidth/2, xmax+xwidth/2)

            self.fig.canvas.draw_idle()
        elif event.key=="t":
            offset = event.xdata
            time = self.start + offset
            amp = event.ydata
            print(f"Time: {time} ({offset})  Amp: {amp}")
        elif event.key=="e":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin+xwidth/2, xmax+xwidth/2)
            self.fig.canvas.draw_idle()
        elif event.key=="w":
            xmin, xmax, ymin, ymax = self.ax.axis()
            xwidth = xmax - xmin
            self.ax.set_xlim(xmin-xwidth/2, xmax-xwidth/2)
            self.fig.canvas.draw_idle()
        elif event.key=="q":
            print("Finished picking")
            self.do_finish("quit")
            self.close()
        elif event.key == "n" or event.key == "v":
            self.do_finish("next")
        elif event.key == "r":
            self.do_finish("prev")
        elif event.key == "c":
            if event.inaxes is not None:
                self.do_pick(event)
        elif event.key == "a" or event.key == "p":
            if event.inaxes is not None:
                self.do_pick(event, phase="P")
        elif event.key == "s":
            if event.inaxes is not None:
                self.do_pick(event, phase="S")
        elif event.key == "d":
            print(self.display_picks())
        elif event.key == "f":
            self.do_filter(self.curr_filter+1)
    def list_channels(self):
        """
        Lists the channel codes for all traces in the stream, removing duplicates.
        Usually all traces will be from a single channel.
        """
        chans = ""
        for tr in self.stream:
            stats = tr.stats
            nslc = f"{stats.network}_{stats.station}_{stats.location}_{stats.channel}"
            if nslc not in chans:
                chans = f"{chans} {nslc}"
        return chans.strip()
    def display_picks(self):
        """
        Creates a string showing the current channels, earthquake and all the
        picks on the current stream.
        """
        s = self.list_channels()
        s += "\n"
        if self.qmlevent is not None:
            s+= f"{self.qmlevent.short_str()}\n"
        for p in self.channel_picks():
            a = self.arrival_for_pick(p)
            pname = a.phase if a is not None else p.phase_hint
            isArr = "" if a is None else "Arrival"
            author = ""
            if p.creation_info.agency_id is not None:
                author += p.creation_info.agency_id+" "
            if p.creation_info.author is not None:
                author += p.creation_info.author+ " "
            author = author.strip()
            s = f"{s}\n{pname} {p.time} {author} {isArr}"
        return s
    def calc_start(self):
        start = self.stream[0].stats.starttime
        for tr in self.stream:
            if tr.stats.starttime < start:
                start = tr.stats.starttime
        return start
