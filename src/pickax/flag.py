from .pick_util import (
    pick_to_string,
    pick_from_trace,
    arrival_for_pick,
    amplitude_for_pick,
    pick_to_multiline,
    remove_pick
    )

class PickFlag:
    def __init__(self, pick, seismograph, arrival=None, is_modifiable=False):
        self.pick = pick
        self.arrival = arrival
        self.seismograph = seismograph
        self.is_modifiable = is_modifiable
        self.press = None
        self.line_artist = None
        self.label_artist = None
        self.color_labelFn = None
        self.canvas = None
    def mouse_event_connect(self, canvas):
        self.canvas = canvas
        if self.is_modifiable:
            self.cidpress = canvas.mpl_connect(
                'button_press_event', self.on_press)
            self.cidrelease = canvas.mpl_connect(
                'button_release_event', self.on_release)
            self.cidmotion = canvas.mpl_connect(
                'motion_notify_event', self.on_motion)
            self.cidkeypress = canvas.mpl_connect('key_press_event', self.on_key)
    def event_on_flag(self, event):
        if self.line_artist is None or self.label_artist is None:
            return
        if event.inaxes != self.line_artist.axes and event.inaxes != self.label_artist.axes:
            return False
        line_contains, line_attrd = self.line_artist.contains(event)
        label_contains, label_attrd = self.label_artist.contains(event)
        return line_contains or label_contains
    def on_key(self, event):
        if event.key == "backspace":
            if self.event_on_flag(event):
                if not self.is_modifiable:
                    print("Unable to remove, pick is not modifiable")
                    return
                if self.seismograph.qmlevent is not None:
                    remove_pick(self.pick, self.seismograph.qmlevent)
                if self in self.seismograph.flags:
                    self.seismograph.flags.remove(self)
                if self.line_artist is not None:
                    self.line_artist.remove()
                    self.line_artist = None
                if self.label_artist is not None:
                    self.label_artist.remove()
                    self.label_artist = None
                self.canvas.draw_idle()
    def on_press(self, event):
        if not self.event_on_flag(event):
            return
        xmin, xmax, ymin, ymax = self.seismograph.ax.axis()
        self.press = (event.xdata, event.ydata, xmin, xmax)
    def on_release(self, event):
        if not self.event_on_flag(event):
            return
        self.press = None
    def on_motion(self, event):
        if self.press is None or event.xdata is None:
            return
        press_xdata, press_ydata, press_xmin, press_xmax = self.press
        if event.xdata < press_xmin or event.xdata > press_xmax:
            # left the draw area so release the motion
            self.press = None
            return
        self.pick.time = self.seismograph.start + event.xdata
        self.draw()
        event.canvas.draw_idle()
    def draw(self):
        if self.line_artist is not None:
            tmp_line_artist = self.line_artist
            self.line_artist = None
            tmp_line_artist.remove()
        if self.label_artist is not None:
            tmp_label_artist = self.label_artist
            self.label_artist = None
            tmp_label_artist.remove()
        start = self.seismograph.start
        ax = self.seismograph.ax
        at_time = self.pick.time - self.seismograph.start
        xmin, xmax, ymin, ymax = ax.axis()
        mean = (ymin+ymax)/2
        hw = 0.9*(ymax-ymin)/2
        x = [at_time, at_time]
        y = [mean-hw, mean+hw]
        color, label_str = self.color_label()
        (ln,) = ax.plot(x,y,color=color, lw=1)
        label = ax.annotate(label_str, xy=(x[1], mean+hw*0.9), xytext=(x[1], mean+hw*0.9),  color=color)
        self.line_artist = ln
        self.label_artist = label
        return ln, label
    def color_label(self):
        color = None
        label_str = None
        if self.color_labelFn is not None:
            color, label_str = self.color_labelFn(self.pick, self.arrival)

        if color is None:
            color = "red"
            if self.arrival is not None:
                color = "blue"

        if label_str is None and self.arrival is not None:
            label_str = self.arrival.phase
        elif label_str is None and self.pick.phase_hint is not None:
            label_str = self.pick.phase_hint
        return color, label_str
