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