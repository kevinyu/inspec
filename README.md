# inspec
View spectrograms of audio data files in the terminal as ascii characters. Provides printing to stdout, a terminal gui built on curses, and importable functions.

## install

```
pip install git@github.com:kevinyu/inspec.git 
```

## compatibility

Definitely works on Ubuntu + Python3.8. Kind of works on Windows 10 + Python3.8 in Powershell but a little unstable, needs `pip install windows-curses` as well.

## cli

Invocation of **inspec** uses the entrypoint **python -m inspec.cli**.

#### inspec open
```
Usage: inspec open [OPTIONS] [FILENAMES]...

  Open interactive gui for viewing audio files in command line

Options:
  -r, --rows INTEGER  Number of rows in layout
  -c, --cols INTEGER  Number of columns in layout
  -t, --time FLOAT    Jump to time in file
  --cmap TEXT         Choose colormap (see list-cmaps for options)
  --help              Show this message and exit.
```

![inspec open demo](demo/inspec_open_demo.gif)

#### inspec show
```
Usage: inspec show [OPTIONS] FILENAME

  Print visual representation of audio file in command line

Options:
  --cmap TEXT           Choose colormap (see list-cmaps for options)
  -d, --duration FLOAT
  -t, --time FLOAT
  --amp                 Show amplitude of signal instead of spectrogram
  --help                Show this message and exit.
```

![inspec show demo](demo/inspec_show_demo.gif)

#### importing in python

The code can be imported so renders can be done dynamically in other programs. This is the current gist but would be nice to make a simpler way to do this.

```python
from inspec.plugins.audio.spectrogram_view import BaseAsciiSpectrogramPlugin

# Printing to stdout
plugin = BaseAsciiSpectrogramPlugin()
plugin.set_cmap("plasma")
plugin.read_file(FILENAME)
plugin.render()
```

## development

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -r requirements.txt
```

Run unittests
```
inspec dev unittests
```

## design notes

### file organization

#### inspec/gui
* main application functions that implement curses

#### inspec/cli.py
* defines commands as entrypoints to invoking programs in main.py

#### inspec/plugins/audio
* different modules for viewing data (time-freq, amlitude, psd, etc)

#### inspec/plugins/colormap.py
* colormaps defined in terminal colors

## todo

* Create a module for live streaming data?

## bugs

* Cant load folder with too many files (tries to create a curses pad that is too wide)
* Reverse lookup of colors in colormap with repeated colors causes errors
