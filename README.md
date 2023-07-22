# inspec

Visually inspect audio files and images from the command line by displaying them as unicode characters.

Includes a cli tool `inspec` to print images/audio/video.

## Quick start

```
pip install inspec
```

```
Usage: inspec [OPTIONS] COMMAND [ARGS]...

Commands:
  imshow  Print an image to stdout
  listen  Listen to audio and print to stdout
  open    Open interactive GUI
  show    Print an audio file to stdout
```

## Dev setup

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -e .
```

Do `pip install -e .[video]` to have imageio ffmpeg support.

Run tests

```
pytest src
```

# Examples

```
inspec show demo/warbling.wav
inspec imshow demo/mandrill.jpg

python -m view.test_view
python -m render.test_render
```

# Outdated commands - will try to reimplement all of these

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

```python
import inspec

# Printing to stdout
inspec.show(FILENAME)
inspec.imshow(FILENAME)

# Open a gui displaying live spectrograms
inspec.listen()
```
