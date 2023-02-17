
import os
from obspy.core.event.base import CreationInfo
from obspy.taup import TauPyModel


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
        self.scroll_factor = 8
        self.author_colors = {}
        self.titleFn = default_titleFn
        self.finishFn = None
        self.creation_info = None
        self.filters = []
        self.phase_list = []
        self._model =  None
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



def default_titleFn(stream=None, qmlevent=None, inventory=None):
    origin_str = "Unknown quake"
    mag_str = ""
    if qmlevent.preferred_origin() is not None:
        origin = qmlevent.preferred_origin()
        origin_str = f"{origin.time} ({origin.latitude}/{origin.longitude}) {origin.depth/1000}km"
    if qmlevent.preferred_magnitude() is not None:
        mag = qmlevent.preferred_magnitude()
        mag_str = f"{mag.mag} {mag.magnitude_type}"
    return f"{origin_str} {mag_str}"

def defaultColorFn(pick, arrival, author_colors):
    # big list of color names here:
    # https://matplotlib.org/stable/gallery/color/named_colors.html
    color = None # none means use built in defaults, red and blue
    if pick is None and arrival is None:
        color = None
    elif arrival is not None:
        # usually means pick used in official location
        color = "blue"
    else:
        pick_author = ""
        if pick.creation_info.agency_id is not None:
            pick_author += pick.creation_info.agency_id+" "
        if pick.creation_info.author is not None:
            pick_author += pick.creation_info.author+ " "
        pick_author = pick_author.strip()
        if pick_author in author_colors:
            color = author_colors[pick_author]
    label_str = None

    if label_str is None and arrival is not None:
        label_str = arrival.phase
    elif label_str is None and pick.phase_hint is not None:
        label_str = pick.phase_hint
    return color, label_str