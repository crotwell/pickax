
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
    def do_finish(self):
        if self.finishFn is not None:
            self.finishFn(self.qmlevent, self.stream)
    def draw(self):
        # make a new figure
        self.fig, self.ax = plt.subplots()
        self.ax.set_xlabel('seconds')
        stats = self.stream[0].stats
        self.ax.set_title(f"Pickaxe {stats.network}_{stats.station}_{stats.location}_{stats.channel}")
        self.bm = BlitManager(self.fig.canvas, [])
        # add lines
        for trace in self.stream:
            (ln,) = self.ax.plot(trace.times(),trace.data,color="black", lw=1, animated=True)
            self.bm.add_artist(ln)
        sta_code = self.stream[0].stats.station
        staPicks = filter(lambda p: p.waveform_id.station_code == sta_code, self.qmlevent.picks)

        for pick in staPicks:
            found = False
            for o in self.qmlevent.origins:
                for a in o.arrivals:
                    if pick.resource_id.id == a.pick_id.id:
                        self.draw_flag(pick, a)
                        found = True
                        break
            if not found:
                self.draw_flag(pick)
#        self.fig.canvas.mpl_connect('button_press_event', lambda evt: self.onclick(evt))
        self.fig.canvas.mpl_connect('key_press_event', lambda evt: self.on_key(evt))

        # make sure our window is on the screen and drawn
        plt.show(block=False)
        plt.pause(.1)
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
    def do_pick(self, event): #Defines what happens when you click on a sesismogram; saves pick to array
        global ix
        ix=event.xdata
        p = obspy.core.event.origin.Pick()
        p.time = self.start + ix
        p.waveform_id = obspy.core.event.base.WaveformStreamID(network_code=self.stream[0].stats.network,
                                                               station_code=self.stream[0].stats.station,
                                                               location_code=self.stream[0].stats.location,
                                                               channel_code=self.stream[0].stats.channel)
        self.qmlevent.picks.append(p)
        self.draw_flag(p)
        self.bm.update()
    def on_key(self, event):  #Defines what happens when you hit a key, Esc = exit + stop code, and Space = stop picking and return picks
        if event.key==" ":
            print("Finished picking, return picks")
            self.do_finish()
            plt.close()
        elif event.key == "p":
            if event.inaxes is not None:
                self.do_pick(event)
