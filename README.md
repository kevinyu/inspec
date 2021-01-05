# inspec
View spectrograms of audio data files in the terminal as ascii characters. Provides printing to stdout, a terminal gui built on curses, and importable functions.

## setup

To install for development

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -r requirements.txt
```

## compatibility

Definitely works on Ubuntu + Python3.8. Kind of works on Windows 10 + Python3.8 in Powershell but a little unstable, needs `pip install windows-curses` as well.

## cli

The **inspec** command at bin/inspec is essentially an alias for **python -m inspec.cli** when the environment is activated with bin/activate. Invocation of **inspec** in the following examples can be replaced by **python -m inspec.cli** while in the virtual environment.

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

#### inspec open
```
Usage: inspec open [OPTIONS] [FILENAMES]...

  Open interactive gui for viewing audio files in command line

Options:
  -r, --rows INTEGER  Number of rows in layout
  -c, --cols INTEGER  Number of columns in layout
  --cmap TEXT         Choose colormap (see list-cmaps for options)
  --show-logs
  --help              Show this message and exit.
```

#### other important commands

```
inspec list-cmaps
inspec dev view-cmap
```

Run unittests 
```
inspec dev unittests
```

#### importing in python

The code can be imported so renders can be done dynamically in other programs. This is the current gist.

```python
from inspec.plugins.audio.spectrogram_view import BaseAsciiSpectrogramPlugin

# Printing to stdout
plugin = BaseAsciiSpectrogramPlugin()
plugin.set_cmap("plasma")
plugin.read_file(FILENAME)
plugin.render()
```

## design notes

### file organization

#### inspec/main.py
* main application functions that implement curses
* manage open files
* keep a global view state and per-file view state in the GUI

#### inspec/cli.py
* defines commands as entrypoints to invoking programs in main.py

#### inspec/plugins/audio
* different modules for viewing data (time-freq, amlitude, psd, etc)

#### inspec/plugins/colormap.py
* colormaps defined in terminal colors

### terminal color encoding

To increase the resolution of rendering images in the y-axis, each terminal row is divided into two pixels using the unicode characters `█`, ` `, `▄`, and `▀`, labeled as `const.FULL_1`, `const.FULL_0`, `const.HALF_01`, and `const.HALF_10` respectively. A pair of these "pixels" being rendered as a single character I call a "patch".

curses has 255 slots for foreground/background color pairs. We assign each SLOT to a (F, B) color where SLOT is a number between 1 and 255 inclusive representing a curses color slot, and F and B are numbers between 0 and 255 inclusive representing terminal colors for the foreground and background respectively. F and B must come from the set of K colors in a colormap.

To increase the capacity of colors per colormap, we note that we never need to use a slot where F == B since we can always just use `█` colored by (F, \*), or ` ` colored using (\*, B). Similarly, we never need to use a slot for F < B. If we wanted a slot colored as `▄` (F, B) with F < B, we can replace it with `▀` (B, F).

Thus we have the following solution so that every possible patch can be encoded in the colormap using a combination of one of `█`, ` `, `▄`, and `▀` and one of our stored (F, B) pairs.

```
COLORS are the K color values in the color map indexed from 0 to K-1 inclusive
SLOTS are the 255 slots from 1 to 255 inclusive
PATCH is a (X0, X1) pair where X0 and X1 are the indices into COLORS that we want to render
```

| PATCH = (X0, X1) | (COLORS, CHAR) | (SLOT, CHAR) |
|---|---|---|
|`(0, 0)`| `(COLORS[K-1], COLORS[0]), " ")` | `(K-1, " ")` |
|`(1, 0)`| `(COLORS[1], COLORS[0]), "▀")` | `(1, "▀")` |
|`(2, 0)`| `(COLORS[2], COLORS[0]), "▀")` | `(2, "▀")` |
|...|...|...|
|`(K-1, 0)`| `(COLORS[K-1], COLORS[0]), "▀")` | `(K-1, "▀")` |
|`(0, 1)`| `(COLORS[1], COLORS[0]), "▄")` | `(2, "▄")` |
|`(1, 1)`| `(COLORS[1], COLORS[0]), "█")` | `(2, "█")` |
|`(2, 1)`| `(COLORS[2], COLORS[1]), "▀")` | `(K, "▀")` |
|...|...|...|
|`(K-1, 1)`| `(COLORS[K-1], COLORS[1]), "▀")` | `(2K-1, "▀")` |
|`(0, 2)`| `(COLORS[2], COLORS[0]), "▄")` | `(3, "▄")` |
|`(1, 2)`| `(COLORS[2], COLORS[1]), "▄")` | `(K+1, "▄")` |
|`(2, 2)`| `(COLORS[2], COLORS[0]), "█")` | `(3, "█")` |
|`(3, 2)`| `(COLORS[3], COLORS[2]), "▀")` | `(2K, "▀")` |
|...|...|...|
|`(K-1, 2)`| `(COLORS[3], COLORS[2]), "▀")` | `(3K-4, "▀")` |
|...|...|...|
|`(K-1, K-1)`| `(COLORS[K-1], COLORS[0]), "█")` | `(K-1, "█")` |

The formula for this is

`SLOT = (X1 * (K - 1)) - (X_1 * (X_1 - 1)) // 2 + X0 - X1`

## todo

* Remove heavy dependencies if possible
    * opencv for spectrogram resizing
* Refactoring application state so that view state (time) is per file
* Refactor visualization code into a swappable/toggleable plugin structure
    * How to select and configure active plugins?
* Create a module for live streaming data (integrate into plugin code?)
    * Or create a new plugin group
