# pickaxe
Seismic phase picker

# Keys

- c create generic, unnamed, pick
- a create pick and set phase_hint to "P"
- s create pick and set phase_hint to "S"
- d to display current picks
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
