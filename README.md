# inspec
View spectrograms of audio data files in the terminal using curses

## setup

```
git clone git@github.com:kevinyu/inspec.git
cd inspec
python -m venv env
source bin/activate
pip install -r requirements.txt
```

## todo

* Remove heavy dependencies if possible
    * soundsig for spectrogram computation
    * opencv for spectrogram resizing
* Refactoring application state so that view state (time) is per file
* Refactor visualization code into a swappable/toggleable plugin structure
    * Convert spectrogram ploting code into a spectrogram_view plugin
    * Create a amplitude_view plugin
* Create a module for live streaming data (integrate into plugin code)
