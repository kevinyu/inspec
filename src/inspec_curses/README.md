# Utilities for working with curses

These utilities are meant to support `inspec`'s curses apps. This module should probably only depend on `render`.

## App context

Keeping some global app context is convenient sometimes. The `inspec_curses.context` module provides some helpers.

* Setting/getting the current colorset with `context.set_active(colors)` and `context.get_active()`
* Rendering an 2D array to the a `curses.window`
* Overriding default `breakpoint()` behavior to make it work okay inside of a curses context.

These functions are supported when the app is run using `context.run_with_stdscr(main)`, where `main(stdscr: curses.window)`.

## Drawing/color functions

Once you call `context.set_active(colors)`, you can draw using those colors with `context.draw` and `context.display`.

```
import colormaps
from inspec_curses import context

colormap = colormaps.get_colormap("viridis")
context.set_active(list(colormap.colors))
context.draw(
  window,
  0,
  0,
  ColoredChar(
    char=chars.FULL_0,
    color=ColorPair(
      fg=colormap.to_color(0.2),
      bg=colormap.to_color(0.8),
    ),
  ),
)
```

We are limited to 22 colors to support (22 + 21 + ... + 1) = 253 color pairs. If we don't care about using color pairs (i.e. we only use the 'Full' character set), we can support up to 247 unique colors. This may make things look a lot better actually...
