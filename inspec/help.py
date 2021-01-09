"""Help strings
"""

help_open = """'inspec open'

See 'inspec open --help' for command line arguments

Open an interactive gui for viewing audio files as a grid in the terminal

Keyboard controls (all prompts can be left blank and will silently reject invalid values)

Global controls
===============
  Close the program                 [q]
  Change selected file              [arrow keys] or [h|j|k|l]
  Zoom out/in in time               [+] and [-]
  Prompt to set display rows        [r]
  Prompt to set display cols (int)  [c]
  Prompt to set timescale (float)   [s]
  Prompt to jump to page (int)      [p]
  Toggle spectrogram/amplitude view [z]

Selected file controls
======================
  Scroll in time                    [shift + arrow keys] or [H|L]
  Prompt to jump to time (seconds)  [t]
  Switch to channel                 [number keys]
    (0 indexed, max 9)
"""

help_listen = """'inspec listen'

See 'inspec listen --help' for command line arguments

Live audio display as text.

Keyboard controls (all prompts can be left blank and will silently reject invalid values)

Global Controls
===============
  Close the program                 [q]
  Increase gain                     [up arrow] or [k]
  Decrease gain                     [down arrow] or [j]
  Zoom in on y scale                [+]
  Zoom out on y scale               [-]
  Prompt to set gain                [g]
    (float in dB, defaults 0)
"""


help_strings = {
    "open": help_open,
    "listen": help_listen,
}
