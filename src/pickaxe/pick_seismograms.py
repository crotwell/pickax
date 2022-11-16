
import obspy
from obspy import read
import matplotlib.pyplot as plt
from .blit_manager import BlitManager


class PickSeis:
    def __init__(self, stream, qmlevent=None, finishFn=None):
        self.stream = stream
        if qmlevent is not None:
            self.qmlevent = qmlevent
        else:
            self.qmlevent = obspy.core.event.Event()
        self.start = self.stream[0].stats.starttime
        self.finishFn = finishFn
        self.creation_info = None
    def do_finish(self):
        if self.finishFn is not None:
            self.finishFn(self.qmlevent, self.stream)
    def draw(self):
        # make a new figure
        self.fig, self.ax = plt.subplots()
        self.bm = BlitManager(self.fig.canvas, [])
        self.ax.set_xlabel('seconds')
        stats = self.stream[0].stats
        self.ax.set_title(f"Pickaxe {self.list_channels()}")
        # add lines
        for trace in self.stream:
            (ln,) = self.ax.plot(trace.times(),trace.data,color="black", lw=1, animated=True)
            self.bm.add_artist(ln)

        for pick in self.channel_picks():
            self.draw_flag(pick, self.arrival_for_pick(pick))
#        self.fig.canvas.mpl_connect('button_press_event', lambda evt: self.onclick(evt))
        self.fig.canvas.mpl_connect('key_press_event', lambda evt: self.on_key(evt))

        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
    def arrival_for_pick(self, pick):
        for o in self.qmlevent.origins:
            for a in o.arrivals:
                if pick.resource_id.id == a.pick_id.id:
                    return a
        return None
    def station_picks(self):
        sta_code = self.stream[0].stats.station
        net_code = self.stream[0].stats.network
        return filter(lambda p: p.waveform_id.network_code == net_code and p.waveform_id.station_code == sta_code, self.qmlevent.picks)
    def channel_picks(self):
        loc_code = self.stream[0].stats.location
        chan_code = self.stream[0].stats.channel
        sta_picks = self.station_picks()
        return filter(lambda p: p.waveform_id.location_code == loc_code and p.waveform_id.channel_code == chan_code, sta_picks)

    def draw_flag(self, pick, arrival=None):
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
        if arrival is not None:
            label = self.ax.text(x[1], mean+hw*0.9, arrival.phase, color=color, animated=True)
        elif pick.phase_hint is not None:
            label = self.ax.text(x[1], mean+hw*0.9, pick.phase_hint, color=color, animated=True)
        else:
            label = self.ax.text(x[1], mean+hw*0.9, "pick")
        self.bm.add_artist(ln)
        self.bm.add_artist(label)
    def do_pick(self, event, phase="pick"): #Defines what happens when you click on a sesismogram; saves pick to array
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
    def on_key(self, event):  #Defines what happens when you hit a key, Esc = exit + stop code, and Space = stop picking and return picks
        if event.key=="q":
            print("Finished picking, return picks")
            self.do_finish()
            plt.close()
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
    def list_channels(self):
        chans = ""
        for tr in self.stream:
            stats = tr.stats
            nslc = f"{stats.network}_{stats.station}_{stats.location}_{stats.channel}"
            if nslc not in chans:
                chans = f"{chans} {nslc}"
        return chans.strip()
    def display_picks(self):
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
