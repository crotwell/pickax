
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
        self.flagcolorFn = None
        self.titleFn = default_titleFn
        self.finishFn = None
        self.creation_info = None
        self.filters = []
        self.phase_list = []
        self._model =  None
        self.figsize=(10,8)
        self.creation_info = CreationInfo(author=os.getlogin())
        print(f"keymap: {self._keymap}")
        for k,v in DEFAULT_KEYMAP.items():
            print(f"{k} -> {v}")
            self._keymap[k] = v

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
