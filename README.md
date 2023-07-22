# inspec

Visually inspect audio files and images from the command line by displaying them as unicode characters.

Tested on `png`, `jpg`, `mp4`, and `wav` files.

## Quick start

```
pip install inspec
```

From command line

```
Usage: inspec [OPTIONS] COMMAND [ARGS]...

Commands:
  imshow  Print an image to stdout
  listen  Listen to audio and print to stdout
  open    Open interactive GUI
  show    Print an audio file to stdout
```

From python

```python
import inspec

inspec.imshow("path/to/image/file.png")
inspec.ashow("path/to/audio/file.wav")
inspec.vshow("path/to/video/file.mp4")
inspec.listen()
```

## Dev setup

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -e .
```

You might need `ffmpeg` for video support not sure tho.

Run tests

```
pytest src
```

# Examples

```shell
inspec show demo/warbling.wav
inspec imshow demo/mandrill.jpg
```
