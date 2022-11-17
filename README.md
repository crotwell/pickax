# PickAxe

PickAxe: a simple seismic picker, when you just need to dig a few
arrivals out of the red clay.

# Start

```
pickaxe -h                   
Hi PickAxe!
usage: pickaxe [-h] [-v] [-l LOADER]

Pickaxe, really simple seismic phase picker.

options:
  -h, --help            show this help message and exit
  -v, --verbose         increase output verbosity
  -l LOADER, --loader LOADER
                        Initialization loader script, run at startup
```

For example, using simple.py to initialize pickaxe, load data and open the picker window:

```
pickaxe -l simple.py
```

# Keys

- c create generic, unnamed, pick
- a (or p) create pick and set phase_hint to "P"
- s create pick and set phase_hint to "S"
- d to display current picks
- f toggle to next filter
- v (or n) save, but don't quite, ie go to next
- x, followed by second x zooms to selected time window
- X, zoom out
- q quit and save

# build hints

```
conda create -n pickaxe python=3.10
conda activate pickaxe
python3 -m pip install --upgrade build
rm dist/* && python3 -m build
pip3 install dist/pickaxe-*-py3-none-any.whl --force-reinstall

```

or if all deps are already installed, much faster:
```
pip3 install dist/pickaxe-*-py3-none-any.whl --force-reinstall --no-deps
```
