# PickAx

[![PyPI](https://img.shields.io/pypi/v/pickax)](https://pypi.org/project/pickax/)

PickAx: a simple seismic picker, when you just need to dig out a few
arrivals.

# Start

```
pickax -h
Hi PickAx!
usage: pickax [-h] [-v] [-l LOADER] [-s SEIS]

Pickax, really simple seismic phase picker.

options:
  -h, --help            show this help message and exit
  -v, --verbose         increase output verbosity
  -l LOADER, --loader LOADER
                        Initialization loader script, run at startup
  -s SEIS, --seis SEIS  Seismogram file, loaded at startup
```

For example, using `simple.py` to initialize pickax, load data and open the picker window:

```
pickax -l simple.py
```

Or to view just a single file, ie quick look:
```
pickax -s JKYD.mseed
```

# Keys

- c create generic, unnamed, pick
- a create pick and set phase_hint to "P"
- s create pick and set phase_hint to "S"
- d/D to display author's picks/ all picks
- f/F toggle to next/prev filter
- v finish current seis, but don't quit, ie go to next
- r finish current seis, go to previous
- x, followed by second x zooms to selected time window
- X, zoom out
- w shift left (west)
- e shift right (east)
- t print current mouse time and amplitude
- q finish current seis and quit

# Configuration

PickAx tries to be very simple and do just one thing, just like
a pickax is good for digging a hole in
red clay, but is just one of the tools in your toolshed. So don't forget
to use your shovels, screwdrivers and lawnmowers for the things they do better.
Basically all data management is handed off to the startup
script. By setting the finishFn, you can save picks however you want (or not
at all), and load in the next seismogram for display. Setting the filters
allows toggling between different ways of processing the seismogram.
The creation_info provides default creation info for the pick,
primarily for author or agency_id, defaulting to `author=os.getlogin()`.

See [simple.py](https://raw.githubusercontent.com/crotwell/pickax/main/simple.py) for an example of setting up pickax and loading data.

# Filter functions

Filters are often a way of applying actual time series filters, but can
be anything that modifies the waveform.
They are each a simple dictionary with a `name` and `fn`.
The function will be called
with four arguments. First is a copy of the original stream, so modification in
place is safe. The second is the current filtered stream, so filters can build
on the previous if that is what you want. Third is the name for the current
filter function, and last is the filter index, just for reference.
If a stream is returned, that becomes
the current displayed stream, but if None is returned, then it assumes
the original was modified in place.

# Finish function

The finish function is called whenever the user quits, goes to next or previous,
ie `q`, `v` or `r`. It is called with three arguments, first is the QuakeML
Event, which contains picks, including both new picks and any existing picks.
Second is the current stream, useful to get the channel. Last is the command,
one of "quit", "next", or "prev".

# build hints

```
conda create -n pickax python=3.10
conda activate pickax
python3 -m pip install --upgrade build
rm -f dist/* && python3 -m build
pip3 install dist/pickax-*-py3-none-any.whl --force-reinstall

```

or if all deps are already installed, much faster:
```
pip3 install dist/pickax-*-py3-none-any.whl --force-reinstall --no-deps
```
