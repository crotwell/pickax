
import os
from obspy.core.event.base import CreationInfo
from obspy.taup import TauPyModel


# remember help.py if adding to keymap
DEFAULT_KEYMAP = {
    'c': "PICK_GENERIC",
    'a': "PICK_P",
    's': "PICK_S",
    'backspace': "REMOVE_PICK",
    'd': "DISPLAY_PICKS",
    'D': "DISPLAY_ALL_PICKS",
    'f': "NEXT_FILTER",
    'F': "PREV_FILTER",
    'y': "AMP_MODE",
    'x': "ZOOM_IN",
    'X': "ZOOM_OUT",
    'z': "ZOOM_ORIG",
    'w': "WEST",
    'e': "EAST",
    't': "CURR_MOUSE",
    'v': "GO_NEXT",
    'r': "GO_PREV",
    'V': "GO_NEXT_QUAKE",
    'R': "GO_PREV_QUAKE",
    '*': "LIST_QUAKES",
    '^': "LIST_STATIONS",
    'q': "GO_QUIT",
    'h': "HELP",
}

TRACE_AMP = "TRACE_AMP"
WINDOW_AMP = "WINDOW_AMP"
GLOBAL_AMP = "GLOBAL_AMP"

class PickAxConfig:
    """
    Configuration for PickAx.

    finishFn -- a callback function for when the next (v) or prev (r) keys are pressed
    creation_info -- default creation info for the pick, primarily for author or agency_id
    filters -- list of filters, f cycles through these redrawing the waveform
    keymap -- optional dictionary of key to function
    """
    def __init__(self):
        self._keymap = {}
        self.debug = False
        self.verbose = False
        self.scroll_factor = 8
        self.author_colors = {}
        self.titleFn = default_titleFn
        self.finishFn = None
        self.seismogram_itr = None
        self.creation_info = None
        self.resource_prefix="smi:pickax"
        self.filters = []
        self.phase_list = []
        self._model =  None
        self.amplitude_mode = TRACE_AMP
        self.figsize=(10,8)
        self.creation_info = CreationInfo(author=os.getlogin())
        for k,v in DEFAULT_KEYMAP.items():
            self._keymap[k] = v
        self.pick_color_labelFn = lambda p,a: defaultColorFn(p, a, self.author_colors)

    @property
    def keymap(self):
        return self._keymap
    @keymap.setter
    def keymap(self, keymap):
        for k,v in keymap.items():
            self._keymap[k] = v
    @property
    def model(self):
        if self._model is None:
            self._model = TauPyModel("ak135")
        return self._model
    @model.setter
    def model(self, model):
        self._model = model
    def toggle_amplitude_mode(self):
        self.amplitude_mode = TRACE_AMP if self.amplitude_mode == GLOBAL_AMP else GLOBAL_AMP



def origin_mag_to_string(qmlevent=None):
    origin_str = "Unknown quake"
    mag_str = ""
    if qmlevent.preferred_origin() is not None:
        origin = qmlevent.preferred_origin()
        origin_str = f"{origin.time} ({origin.latitude}/{origin.longitude}) {origin.depth/1000}km"
    if qmlevent.preferred_magnitude() is not None:
        mag = qmlevent.preferred_magnitude()
        mag_str = f"{mag.mag} {mag.magnitude_type}"
    return f"{origin_str} {mag_str}".strip()

def default_titleFn(stream=None, qmlevent=None, inventory=None):
    return origin_mag_to_string(qmlevent)

def defaultColorFn(pick, arrival, author_colors):
    pick_author = ""
    if pick.creation_info is not None:
        if pick.creation_info.author is not None:
            pick_author = pick.creation_info.author
        elif pick.creation_info.agency_id is not None:
            pick_author = pick.creation_info.agency_id
    pick_author = pick_author.strip()

    # big list of color names here:
    # https://matplotlib.org/stable/gallery/color/named_colors.html

    color = None # none means use built in defaults, red and blue
    if pick is None and arrival is None:
        color = None
    elif arrival is not None:
        # usually means pick used in official location
        color = "blue"
    else:
        if pick_author in author_colors:
            color = author_colors[pick_author]
    label_str = None

    if arrival is not None:
        label_str = arrival.phase
    if label_str is None and pick.phase_hint is not None:
        label_str = pick.phase_hint
    if label_str is None:
        label_str = "unknown phase"
    return color, label_str
