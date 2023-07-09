# inspec

Inspect audio files and images from the command line by displaying them as unicode characters.

Primary purpose is to inspect media files on a server during a remote SSH session or to quickly spot-check files during a script. Provides printing to stdout, a terminal gui built with curses, and importable Python functions.

## Install

```
pip install inspec
```

## Usage

### Command Line

Launch the GUI viewer for audio files and image files respectively. At some point I probably want to merge these two commands and infer the file type from the extensions.
```shell
inspec open FILENAME [-r ROWS] [-c COLS] [--cmap CMAP]
inspec imopen FILENAME [-r ROWS] [-c COLS] [--cmap CMAP]
```

Print a file to stdout, inferring type of file base on extension and contents (audio and image versions)
```shell
inspec show FILENAME [-w WIDTH] [-h HEIGHT] [--cmap CMAP] [--horizontal OR --vertical]
inspec imshow FILENAME [-w WIDTH] [-h HEIGHT] [--cmap CMAP] [--horizontal OR --vertical]
```

Show a live spectrogram or amplitude of an input device
```shell
inspec listen [-d DEVICE] [-c CHANNELS] [-m 'spec' OR 'amp'] [--cmap CMAP]
```

```shell
inspec list-devices
inspec list-cmaps
```

![inspec open demo](demo/inspec_open_demo.gif)

![inspec show demo](demo/inspec_show_demo.gif)

### 'inspec open' and 'inspec imopen' commands

**General controls**

| Action                             |Key|
|---|---|
|  Close the program                 |[q]|
|  Change selected file              |[arrow keys] or [h,j,k,l] |
|  Prompt to set display rows        |[r]|
|  Prompt to set display cols (int)  |[c]|
|  Prompt to jump to page (int)      |[p]|

**Audio only**

| Action                             |Key|
|---|---|
|  Zoom out/in in time               |[+]| and [-]|
|  Prompt to set timescale (float)   |[s]|
|  Toggle spectrogram/amplitude view |[z]|
|  Scroll file in time                    |[shift + arrow keys] or [H,L]|
|  Prompt to jump to time (seconds)  |[t]|
|  Switch to channel (0 indexed, max 9) |[number keys]|

**Images only**

| Action                             |Key|
|---|---|
|  Toggle thumbnail (lower resolution) |[z]|

### 'inspec listen' commands

| Action                             |Key|
|---|---|
|  Close the program                 |[q]|
|  Increase gain                     |[up arrow] or [k] |
|  Decrease gain                     |[down arrow] or [j]|
|  Zoom in on y scale                |[+]|
|  Zoom out on y scale               |[-]|
|  Prompt to set gain (float in dB, defaults 0) |[g]|


### Python

Convenience methods mirroring the cli

```python
import inspec

# Open a terminal gui
inspec.open_gui(FILENAMES, rows=2, cols=2, cmap="viridis")
inspec.open_image_gui(FILENAMES, rows=4, cols=3, cmap="greys")

# Printing to stdout
inspec.show(FILENAME, width=0.5, height=0.5)
inspec.imshow(FILENAME, width=0.5, height=0.5)

# Open a gui displaying live spectrograms
inspec.listen(device=DEVICE, channels=1)
```

## Development

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -e .
```

Run unittests
```
inspec dev unittests
```

#### Rendering data

For more fine-grained control, or to extend the visualizations to other data formats, you can add/modify/remove intermediate processing steps. These are

1. reading in data (`inspec.io`)

2. converting to 2D image array (`inspec.transform`)

3. converting image data into 2d array of unicode characters and foreground/background scale values between 0 and 1 (`inspec.maps`)

4. applying a colormap to the colors, converting into a 2d array of unicode characters and foreground/background color values (`StdoutRenderer.apply_colormap_to_char_array()`)

3. and then displaying those characters. (`StdoutRenderer.render()`)

```python
import inspec
from inspec.colormap import load_cmap
from inspec.io import AudioReader
from inspec.maps import get_map
from inspec.render import StdoutRenderer
from inspec.transform import SpectrogramTransform

cmap = load_cmap("viridis")
transform = SpectrogramTransform(1000, 50, min_freq=250, max_freq=10000)

data, sampling_rate, _ = AudioReader.read_file("sample.wav")

# Convert the data into a 2D image
img, _ = transform.convert(data, sampling_rate, output_size=(80, 160))

# Convert the image into tuples of unicode characters and colors to map (from 0. to 1.)
char_img = get_map("quarter").to_char_array(img)

# Apply a colormap to the 0. to 1. colors into terminal color values (or curses colors)
char_img_colorized = StdoutRenderer.apply_cmap_to_char_array(cmap, char_img)

# Display the characters and colors to the screen
StdoutRenderer.display(char_img_colorized)
```

#### GUI

The main GUI is built on **asyncio** and **curses**. The base class is in `inspec.gui.base`

```python
import curses
from inspec.gui.base import InspecCursesApp

def _run(stdscr):
    app = InspecCursesApp(refresh_rate=40, debug=True)
    asyncio.run(app.main(stdscr))

curses.wrapper(_run)
```

The main methods that should be implemented in an app derived from `InspecCursesApp` are `refresh()`, `initialize_display()`, and `handle_key(ch)`. See examples in `inspec/develop/example_apps.py`.

## Compatibility

Definitely works on Ubuntu + Python3.8. Kind of works on Windows 10 + Python3.8 in Powershell but a little unstable, needs `pip install windows-curses` as well.

## Todo

* Simpler API to view data from data structures instead of reading from disk
* Debouncing key inputs in gui (throttle holding arrow keys, scroll wheel, etc)
* Cleaning up parameters for functions in inspec/inspec.py and their corresponding cli commands in inspec/cli.py
* Better documentation
* Error handling for unreadable files, non-audio files
* RGB colormaps and rendering

## To fix
* Images in --vertical mode display backwards
* Spectrogram artifacts in listen mode
* Consolidate commands for image and audio files into the same command and just be smart about file types/extensions?
