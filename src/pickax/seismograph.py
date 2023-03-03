import sys
import os
import re
import obspy
import numpy
from obspy import read
from IPython import get_ipython
from prompt_toolkit.application.current import get_app

from .pick_util import (
    pick_to_string,
    pick_from_trace,
    arrival_for_pick,
    create_pick_on_stream
    )
from .pickax_config import TRACE_AMP, GLOBAL_AMP

# reg exp to find/replace whitespace in ids
zap_space = re.compile(r'\s+')

class Seismograph:
    """
    Single display for seismograms. If there are more than one seismogram, they
    are displayed overlain.

    ax -- matplotlib ax for display
    stream -- usually a waveform for a single channel
    config -- pickax_config for configuration of display
    qmlevent -- optional QuakeML Event to store picks in, created if not supplied
    traveltime_calc -- option predicted travel time calculator
    """
    def __init__(self,
                 ax,
                 stream,
                 config,
                 qmlevent=None,
                 inventory=None,
                 traveltime_calc = None,
                ):
        self._trace_artists = []
        self._flag_artists = []
        self._zoom_bounds = []
        self.flags = []
        self.ax = ax
        self.config = config
        self.inventory = inventory
        self.traveltime_calc = traveltime_calc
        self._init_data_(stream, qmlevent)
        self._prev_zoom_time = None
        self.ylim = None
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
        if self.config.amplitude_mode == TRACE_AMP:
            self.ax.set_ylim(auto=True)
        else:
            if self.ylim == None:
                self.ylim = self.calc_zoom_amp()
            self.ax.set_ylim(*self.ylim)
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
        for pick_flag in self.flags:
            pick_flag.draw()
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

    def draw_predicted_flags(self):
        """
        Calculate and draw flags for predicted arrivals.
        """
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
                    if self.config.verbose:
                        print("can't find inv for tr")
    def do_pick(self, event, phase="pick"):
        """
        Creates a pick based on a gui event, like keypress and mouse position.
        Optionally give the pick a phase name, defaults to "pick".
        """
        filter_name = None
        if self.curr_filter != -1:
            filter_name = self.config.filters[self.curr_filter]['name']
            filter_name = re.sub(zap_space, '_', filter_name)
        pick, amp = create_pick_on_stream(self.stream,
                                       self.start + event.xdata,
                                       phase,
                                       resource_prefix=self.config.resource_prefix,
                                       creation_info=self.config.creation_info,
                                       filter_name=filter_name)

        self.qmlevent.picks.append(pick)
        self.qmlevent.amplitudes.append(amp)
        return pick
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
        return ln, label
    def do_filter(self, idx):
        """
        Applies the idx-th filter to the waveform and redraws.
        """
        self.clear_trace()
        self.clear_flags()
        if idx < 0 or idx >= len(self.config.filters):
            self._filtered_stream = self.stream
            self.curr_filter = -1
            self.ax.set_ylabel("")
        else:
            filterFn = self.config.filters[idx]['fn']
            orig_copy = self.stream.copy()
            out_stream = filterFn(orig_copy, self._filtered_stream, self.config.filters[idx]['name'], idx, self.inventory, self.qmlevent )
            if out_stream is not None:
                # fun returned new stream
                self._filtered_stream = out_stream
            else:
                # assume filtering done in place
                self._filtered_stream = orig_copy
            self.ax.set_ylabel(self.config.filters[idx]['name'])
            self.curr_filter = idx

        self.zoom_amp()
    def calc_amplitude_range(self, tmin=0, tmax=0):
        tstart = self.start + tmin
        tend = self.start + tmax
        st = self._filtered_stream if self._filtered_stream is not None else self.stream
        if len(st) == 0 or len(st[0]) == 0:
            return None, None
        calc_min = st[0][0]
        calc_max = st[0][0]
        for tr in st:
            tr_slice = tr.slice(tstart, tend) if tmin < tmax else tr
            if tr_slice is not None and tr_slice.data is not None and len(tr_slice.data) > 0:
                calc_min = min(calc_min, tr_slice.data.min())
                calc_max = max(calc_max, tr_slice.data.max())
        if calc_min > calc_max:
            # in case no trace in window
            t = calc_max
            calc_max = calc_min
            calc_min = t
        return (calc_min, calc_max)
    def calc_zoom_amp(self):
        xmin, xmax, ymin, ymax = self.ax.axis()
        calc_min, calc_max = self.calc_amplitude_range(xmin, xmax)
        if calc_min == None or calc_max == None:
            # in case no trace in window
            calc_max = ymax
            calc_min = ymin
        return (calc_min, calc_max)
    def zoom_amp(self):
        if self.ylim == None:
            calc_min, calc_max = self.calc_zoom_amp()
            self.ax.set_ylim(calc_min, calc_max)
        else:
            self.ax.set_ylim(*self.ylim)
        self.refresh_display()
    def unset_ylim(self):
        self.ylim = None
        self.ax.set_ylim(auto=True)
        self.refresh_display()
    def set_ylim(self, min_amp, max_amp):
        self.ylim = (min_amp, max_amp)
        self.ax.set_ylim(*self.ylim)
        self.refresh_display()
    def set_xlim(self, start, end):
        self.xlim = (start, end)
        self.ax.set_xlim(*self.xlim)
        self.refresh_display()
    def unset_xlim(self):
        self.xlim = None
        self.ax.set_xlim(auto=True)
        self.refresh_display()
    def refresh_display(self):
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
                self.set_xlim(self._prev_zoom_time, event.xdata)
            else:
                self.set_xlim(event.xdata, self._prev_zoom_time)
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
        self.set_xlim(xmin-xwidth/2, xmax+xwidth/2)
        self.zoom_amp()
        self.unset_zoom_bound()
    def do_zoom_original(self):
        self.unset_xlim()
        if self.config.amplitude_mode == TRACE_AMP:
            self.unset_ylim()
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
        self.set_xlim(xmin, xmax)
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
