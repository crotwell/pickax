import sys
import os
import obspy
import numpy
from obspy import read
from IPython import get_ipython
from prompt_toolkit.application.current import get_app

from .pick_util import pick_to_string, pick_from_trace, arrival_for_pick


class Seismograph:
    """
    Single display for seismograms. If there are more than one seismogram, they
    are displayed overlain.

    stream -- usually a waveform for a single channel
    qmlevent -- optional QuakeML Event to store picks in, created if not supplied
    finishFn -- a callback function for when the next (v) or prev (r) keys are pressed
    creation_info -- default creation info for the pick, primarily for author or agency_id
    filters -- list of filters, f cycles through these redrawing the waveform
    keymap -- optional dictionary of key to function
    """
    def __init__(self,
                 ax,
                 stream,
                 qmlevent=None,
                 inventory=None,
                 finishFn=None,
                 creation_info=None,
                 filters = [],
                 traveltime_calc = None,
                 keymap = {}, ):
        self._trace_artists = []
        self._flag_artists = []
        self._zoom_bounds = []
        self.ax = ax
        self.finishFn = finishFn
        self.creation_info = creation_info
        self.filters = filters
        self.inventory = inventory
        self.traveltime_calc = traveltime_calc
        self._init_data_(stream, qmlevent)
        if creation_info is None and os.getlogin() is not None:
            self.creation_info = obspy.core.event.base.CreationInfo(
                author=os.getlogin()
                )
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
        if qmlevent is not None:
            self._init_data_(stream, qmlevent)
        else:
            # reuse current event
            self._init_data_(stream, self.qmlevent)
        self.clear_trace()
        self.clear_flags()
        self.ax.clear()
        self.draw()
    def __saved_update_draw(self):
        self.draw_stream()
        self.draw_all_flags()
        self.ax.set_ylabel("")

        self.ax.relim()
    def draw(self):
        self.ax.clear()
        self.ax.set_xlabel(f'seconds from {self.start}')
        stats = self.stream[0].stats
        self.ax.set_title(self.list_channels())
        # add lines
        self.draw_stream()
        self.draw_all_flags()
    def draw_stream(self):
        filt_stream = self._filtered_stream if self._filtered_stream is not None else self.stream
        for trace in filt_stream:
            (ln,) = self.ax.plot(trace.times()+(trace.stats.starttime - self.start),trace.data,color="black", lw=0.5)
            self._trace_artists.append(ln)
    def draw_all_flags(self):
        self.clear_flags()
        self.draw_predicted_flags()
        for pick in self.channel_picks():
            self.draw_pick_flag(pick, arrival_for_pick(pick, self.qmlevent))
        self.draw_origin_flag()
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
    def draw_origin_flag(self):
        """
        Draws flag for the origin.
        """
        if self.qmlevent is not None and self.qmlevent.preferred_origin() is not None:
            self.draw_flag(self.qmlevent.preferred_origin().time, "origin", color="green")

    def draw_pick_flag(self, pick, arrival=None):
        """
        Draws flag for a pick.
        """

        color = "red"
        if arrival is not None:
            color = "blue"

        label_str = "pick"
        if arrival is not None:
            label_str = arrival.phase
        elif pick.phase_hint is not None:
            label_str = pick.phase_hint
        self.draw_flag(pick.time, label_str, color=color)
    def draw_predicted_flags(self):
        if self.traveltime_calc is not None \
                 and self.qmlevent is not None \
                and self.qmlevent.preferred_origin() is not None:
            otime = self.qmlevent.preferred_origin().time
            filt_stream = self._filtered_stream if self._filtered_stream is not None else self.stream
            for trace in filt_stream:
                tr_inv = self.find_channel(trace)
                if tr_inv is not None and len(tr_inv) > 0 and len(tr_inv[0]) > 0:
                    sta = tr_inv[0][0]  # first sta in first net
                    arrivals = self.traveltime_calc.calculate(sta, self.qmlevent)
                    for arr in arrivals:
                        self.draw_flag(otime + arr.time, arr.name, "grey")
                else:
                    print("can't find inv for tr")
    def do_pick(self, event, phase="pick"):
        """
        Creates a pick based on a gui event, like keypress and mouse position.
        Optionally give the pick a phase name, defaults to "pick".
        """
        p = obspy.core.event.origin.Pick()
        p.method_id = "PickAx"
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
        a = None
        for tr in self.stream:
            times = tr.times()
            index = round(times.searchsorted(event.xdata))
            if index >=0 and index < len(tr):
                a = obspy.core.event.magnitude.Amplitude()
                a.generic_amplitude = tr.data[index]
                a.pick_id = p.resource_id
                a.waveform_id = p.waveform_id
                if self.curr_filter != -1:
                    a.filter_id = self.filters[self.curr_filter]['name']
                a.creation_info = p.creation_info
                self.qmlevent.amplitudes.append(a)
                break
        self.draw_pick_flag(p)
    def clear_trace(self):
        """
        Clears the waveforms from the display.
        """
        for artist in self._trace_artists:
            artist.remove()
            self._trace_artists.remove(artist)
    def clear_flags(self):
        """
        Clears pick flags from the display.
        """
        for artist in self._flag_artists:
            artist.remove()
            self._flag_artists.remove(artist)
        # also clear x zoom marker if present
        self.unset_zoom_bound()
    def draw_flag(self, time, label_str, color="black"):
        at_time = time - self.start
        xmin, xmax, ymin, ymax = self.ax.axis()
        mean = (ymin+ymax)/2
        hw = 0.9*(ymax-ymin)/2
        x = [at_time, at_time]
        y = [mean-hw, mean+hw]
        (ln,) = self.ax.plot(x,y,color=color, lw=1)
        label = None
        label = self.ax.annotate(label_str, xy=(x[1], mean+hw*0.9), xytext=(x[1], mean+hw*0.9),  color=color)
        self._flag_artists.append(ln)
        self._flag_artists.append(label)
    def do_filter(self, idx):
        """
        Applies the idx-th filter to the waveform and redraws.
        """
        self.clear_trace()
        self.clear_flags()
        if idx < 0 or idx >= len(self.filters):
            self._filtered_stream = self.stream
            self.curr_filter = -1
            self.ax.set_ylabel("")
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
            self.ax.set_ylabel(self.filters[idx]['name'])
            self.curr_filter = idx

        self.zoom_amp()

    def zoom_amp(self):
        xmin, xmax, ymin, ymax = self.ax.axis()
        calc_min = ymax
        calc_max = ymin
        tstart = self.start + xmin
        tend = self.start + xmax
        st = self._filtered_stream if self._filtered_stream is not None else self.stream
        for tr in st:
            tr_slice = tr.slice(tstart, tend)
            if tr_slice is not None and tr_slice.data is not None and len(tr_slice.data) > 0:
                calc_min = min(calc_min, tr_slice.data.min())
                calc_max = max(calc_max, tr_slice.data.max())
        if calc_min > calc_max:
            # in case no trace in window
            t = calc_max
            calc_max = calc_min
            calc_min = t
        self.ax.set_ylim(calc_min, calc_max)
        self.clear_flags()
        self.clear_trace()
        self.draw_stream()
        self.draw_all_flags()
    def unset_zoom(self):
        self._prev_zoom_time = None
        self.unset_zoom_bound()
    def do_zoom(self, event):
        # event.key=="x":
        if self._prev_zoom_time is not None:
            self.unset_zoom_bound()
            if event.xdata > self._prev_zoom_time:
                self.ax.set_xlim(left=self._prev_zoom_time, right=event.xdata)
            else:
                self.ax.set_xlim(left=event.xdata, right=self._prev_zoom_time)
            self.zoom_amp()
            self._prev_zoom_time = None
        else:
            self._prev_zoom_time = event.xdata
            xmin, xmax, ymin, ymax = self.ax.axis()
            mean = (ymin+ymax)/2
            hw = 0.9*(ymax-ymin)/2
            x = [event.xdata, event.xdata]
            y = [mean-hw, mean+hw]
            color = "black"
            (ln,) = self.ax.plot(x,y,color=color, lw=1)
            self.set_zoom_bound(ln)

    def do_zoom_out(self):
        xmin, xmax, ymin, ymax = self.ax.axis()
        xwidth = xmax - xmin
        self.ax.set_xlim(xmin-xwidth/2, xmax+xwidth/2)
        self.zoom_amp()
        self.unset_zoom_bound()
    def do_zoom_original(self):
        self.ax.set_xlim(auto=True)
        self.ax.set_ylim(auto=True)
        self.unset_zoom_bound()
        self.clear_flags()
        self.clear_trace()
        self.draw_stream()
        self.draw_all_flags()
    def set_zoom_bound(self, art):
        self._zoom_bounds = [art]
    def unset_zoom_bound(self):
        for a in self._zoom_bounds:
            a.remove()
        self._zoom_bounds = []

    def mouse_time_amp(self, event):
        offset = event.xdata
        time = self.start + offset
        amp = event.ydata
        return time, amp, offset
    def update_xlim(self, xmin, xmax):
        self.ax.set_xlim(xmin, xmax)
        self.zoom_amp()
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
    def find_channel(self, tr):
        if self.inventory is None:
            print("Seismograph inv is None")
            return None
        net_code = tr.stats.network
        sta_code = tr.stats.station
        loc_code = tr.stats.location
        chan_code = tr.stats.channel
        return self.inventory.select(network=net_code,
                                  station=sta_code,
                                  location=loc_code,
                                  channel=chan_code,
                                  time=tr.stats.starttime,
                                  )
    def calc_start(self):
        if self.qmlevent is not None and self.qmlevent.preferred_origin() is not None:
            return self.qmlevent.preferred_origin().time
        return min([trace.stats.starttime for trace in self.stream])
