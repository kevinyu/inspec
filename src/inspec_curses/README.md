# Drawing with curses

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