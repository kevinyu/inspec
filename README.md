# inspec

Visually inspect audio files and images from the command line by displaying them as unicode characters.

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

```shell
inspec show demo/warbling.wav
inspec imshow demo/mandrill.jpg
```
