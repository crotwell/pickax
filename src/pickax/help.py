from .version import __version__

keymap_desc = {
    'PICK_GENERIC': "Create a generic pick at the current mouse location",
    'PICK_P': "Create a P pick at the current mouse location",
    'PICK_S': "Create a S pick at the current mouse location",
    'DISPLAY_PICKS': "Display your picks",
    'DISPLAY_ALL_PICKS': "Display all picks",
    'NEXT_FILTER': "Apply next filter",
    'PREV_FILTER': "Apply previous filter",
    'GO_NEXT': "Go to next data",
    'GO_PREV': "Go to previous data",
    'GO_QUIT': "Quit",
    'ZOOM_IN': "Zoom in, first use marks one edge, second zooms in",
    'ZOOM_OUT': "Zoom back out, double time displayed",
    'ZOOM_ORIG': "Return to original autozoom",
    'WEST': "Shift seismogram to left (west)",
    'EAST': "Shift seismogram to right (east)",
    'CURR_MOUSE': "Print current time, amplitude at mouse position",
    'HELP': "Display this help, but you knew that, right?",
}

def print_help(keymap):
    print(f"Pickax {__version__}")
    print()
    print("Keys:")
    for k in keymap:
        desc = keymap_desc[keymap[k]] if keymap[k] in keymap_desc else "Oops, unknown key"
        print(f"  {k}: {desc}")
    print()
