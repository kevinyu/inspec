import abc
import asyncio
import curses
import os
from typing import Generic, Optional, TypeVar

import pydantic
from colormaps import get_colormap
from inspec_app import draw
from inspec_app import events
from inspec_app import key_handlers
from inspec_app.paginate import GridPaginator
from inspec_core.base_view import ViewT
from inspec_core.basic_audio_view import BasicAudioReader, BasicAudioView
from inspec_core.basic_image_view import BasicImageView, GreyscaleImageReader
from inspec_curses import context
from render.renderer import Renderer, make_intensity_renderer
from render.types import RGB, CharShape, Intensity

HELP_MESSAGE = "[q] Quit [l] Next page [h] Previous page [?] Help"
T = TypeVar("T", Intensity, RGB)
FileReaderT = TypeVar("FileReaderT", BasicAudioReader, GreyscaleImageReader)


class ComponentView(pydantic.BaseModel, Generic[T, FileReaderT, ViewT], abc.ABC):
    file_: FileReaderT
    state: ViewT

    class Config:
        arbitrary_types_allowed = True


class AudioComponentView(ComponentView[Intensity, BasicAudioReader, BasicAudioView]):
    pass


class ImageComponentView(
    ComponentView[Intensity, GreyscaleImageReader, BasicImageView]
):
    pass


SupportedComponent = AudioComponentView | ImageComponentView


class GridState(pydantic.BaseModel):
    rows: int = 1
    cols: int = 1


class PanelAppState(pydantic.BaseModel):
    grid: GridState = GridState()
    current_page: int = 0
    active_component_idx: int = 0  # Index into components
    components: list[SupportedComponent]

    # More configy
    poll_interval: float = 0.02

    class Config:
        arbitrary_types_allowed = True

    @property
    def paginator(self) -> GridPaginator:
        return GridPaginator(
            rows=self.grid.rows,
            cols=self.grid.cols,
        )


def render_window_with_border(
    window: curses.window,
    component: SupportedComponent,
    renderer: Renderer[Intensity],
    solid: bool = False,
) -> None:
    _, inner_window = draw.make_border(window, solid=solid)

    # component.file_.filename
    window.addstr(0, 1, component.file_.filename)

    size = draw.size_from_window(inner_window)
    size.height *= renderer.scale().height
    size.width *= renderer.scale().width

    context.display(
        inner_window,
        renderer.apply(
            # This call works as long as we ensure that the component file_ and state types align.
            component.file_.get_view(component.state, size),  # type: ignore
        ),
    )


class Windows(pydantic.BaseModel):
    main: curses.window
    status: curses.window
    debug: curses.window
    grid: list[curses.window]

    class Config:
        arbitrary_types_allowed = True


def apply_layout(stdscr: curses.window, state: PanelAppState) -> Windows:
    main_window, status_window, debug_window = draw.layout_1d(
        stdscr,
        [draw.Span.Stretch(1), draw.Span.Fixed(1), draw.Span.Fixed(1)],
        direction=draw.Direction.Column,
    )
    grid_windows = draw.layout_grid(main_window, state.grid.rows, state.grid.cols)

    return Windows(
        main=main_window,
        status=status_window,
        debug=debug_window,
        grid=grid_windows,
    )


async def run(
    stdscr: curses.window,
    components: list[SupportedComponent],
    rows: int = 1,
    cols: int = 1,
) -> None:
    stdscr.nodelay(True)
    curses.use_default_colors()

    loop = asyncio.get_running_loop()
    state = PanelAppState(
        grid=GridState(
            rows=rows,
            cols=cols,
        ),
        components=components,
    )
    layout = apply_layout(stdscr, state)
    grid_layout_stack: list[GridState] = [state.grid]
    current_handler: key_handlers.KeyHandler = key_handlers.default_handler

    cmap = get_colormap("greys")
    renderer = make_intensity_renderer(cmap, shape=CharShape.Half)
    context.set_active(list(cmap.colors))

    keys_queue = asyncio.Queue()
    events_queue = asyncio.Queue()

    def update_state(
        grid: Optional[GridState] = None,
        current_page: Optional[int] = None,
        active_component_idx: Optional[int] = None,
        components: Optional[list[SupportedComponent]] = None,
    ) -> None:
        nonlocal state
        if all(v is None for v in (grid, current_page, active_component_idx, components)):
            return

        new_state = state.model_copy()
        if grid is not None:
            new_state.grid = grid
            if current_page is None:
                new_state.current_page = new_state.paginator.locate(state.active_component_idx).page
        if current_page is not None:
            new_state.current_page = current_page
        if active_component_idx is not None:
            new_state.active_component_idx = active_component_idx
        if components is not None:
            new_state.components = components

        state = new_state

    async def listen_for_keys() -> None:
        """
        Should be run in a separate thread.
        """
        while True:
            ch: int = stdscr.getch()
            assert ch is not None
            if ch != -1:
                loop.call_soon_threadsafe(keys_queue.put_nowait, ch)
            await asyncio.sleep(state.poll_interval)

    def log(msg: str) -> None:
        _, max_x = layout.debug.getmaxyx()
        msg = msg[: max_x - 2]
        layout.debug.clear()
        layout.debug.addstr(0, 1, msg)
        layout.debug.refresh()

    def status(msg: str) -> None:
        _, max_x = layout.status.getmaxyx()
        msg = msg[: max_x - 2]
        layout.status.clear()
        layout.status.addstr(0, 1, msg)
        layout.status.refresh()

    def redraw(window_idxs: Optional[set[int]] = None) -> None:
        slice_ = state.paginator.page_slice(state.current_page)
        page_components = state.components[slice_]

        for i, window in enumerate(layout.grid):
            component_idx = slice_.start + i
            if window_idxs is not None and i not in window_idxs:
                continue

            window.clear()
            if i >= len(page_components):
                window.refresh()
                continue

            render_window_with_border(
                window,
                page_components[i],
                renderer,
                solid=component_idx == state.active_component_idx,
            )
            window.refresh()

    def set_selection(idx: int) -> None:
        # TODO: this is really hacky.
        position = state.paginator.locate(idx)
        if position.page != state.current_page:
            state.current_page = position.page
            state.active_component_idx = idx
            redraw()
            return

        old_position = state.paginator.locate(state.active_component_idx)
        old_window_idx = old_position.col + old_position.row * state.grid.cols
        new_window_idx = position.col + position.row * state.grid.cols
        state.active_component_idx = idx
        redraw(window_idxs={old_window_idx, new_window_idx})

    async def key_handler_task() -> None:
        while True:
            ch = await keys_queue.get()
            events_queue.put_nowait(current_handler.handle(ch))

    handler_task = loop.create_task(key_handler_task())
    key_listener = loop.create_task(listen_for_keys())

    try:
        redraw()
        set_selection(state.active_component_idx)
        while True:
            event = await events_queue.get()
            if isinstance(event, events.QuitEvent):
                break
            elif isinstance(event, events.NextPageEvent):
                update_state(current_page=(state.current_page + 1) % state.paginator.n_pages(
                    len(state.components)
                ))
                redraw()
            elif isinstance(event, events.PrevPageEvent):
                update_state(current_page=(state.current_page - 1) % state.paginator.n_pages(
                    len(state.components)
                ))
                redraw()
            elif isinstance(event, events.LogEvent):
                log(event.msg)
            elif isinstance(event, events.WindowResized):
                curses.resizeterm(*stdscr.getmaxyx())
                layout = apply_layout(stdscr, state)
                redraw()
            elif isinstance(event, events.Move.Right):
                set_selection(
                    min(state.active_component_idx + 1, len(state.components) - 1)
                )
            elif isinstance(event, events.Move.Left):
                set_selection(max(state.active_component_idx - 1, 0))
            elif isinstance(event, events.Move.Up):
                set_selection(max(state.active_component_idx - state.grid.cols, 0))
            elif isinstance(event, events.Move.Down):
                set_selection(
                    min(
                        state.active_component_idx + state.grid.cols,
                        len(state.components) - 1,
                    )
                )
            elif isinstance(event, events.Select):
                if state.grid.rows == 1 and state.grid.cols == 1:
                    continue
                new_grid = GridState(rows=1, cols=1)
                update_state(
                    grid=new_grid,
                    current_page=state.active_component_idx,
                )
                grid_layout_stack.append(new_grid)
                layout = apply_layout(stdscr, state)
                redraw()
                current_handler = key_handlers.zoom_handler
            elif isinstance(event, events.Undo):
                log(f"Undoing gird selection {grid_layout_stack}")
                if len(grid_layout_stack) > 1:
                    grid_layout_stack.pop()
                    new_grid = grid_layout_stack[-1]
                    update_state(grid=new_grid)
                    layout = apply_layout(stdscr, state)
                    layout.main.clear()
                    status(f"New grid {new_grid}")
                    redraw()
                current_handler = key_handlers.default_handler
            else:
                log(f"Unknown event {event}")
    except KeyboardInterrupt:
        pass
    finally:
        handler_task.cancel()
        key_listener.cancel()


def expand_folders(files: list[str], recursive: bool = False) -> list[str]:
    """
    Expands directories into file lists
    """
    expanded: list[str] = []
    for f in files:
        if os.path.isdir(f):
            expanded.extend(
                os.path.join(f, sub_f)
                for sub_f in os.listdir(f)
                if os.path.isfile(os.path.join(f, sub_f))
            )
        else:
            expanded.append(f)
    return expanded


def resolve_component(filename: str) -> Optional[SupportedComponent]:
    if filename.endswith(".wav"):
        return AudioComponentView(
            file_=BasicAudioReader(filename=filename),
            state=BasicAudioView(),
        )
    elif filename.endswith(".png") or filename.endswith(".jpg"):
        return ImageComponentView(
            file_=GreyscaleImageReader(filename=filename),
            state=BasicImageView(),
        )
    else:
        return None


def main(files: list[str], rows: int = 1, cols: int = 1) -> None:
    files = expand_folders(files)
    components = [component for f in files if (component := resolve_component(f))]

    def run_fn(stdscr: curses.window) -> None:
        asyncio.run(run(stdscr, rows=rows, cols=cols, components=components))

    curses.wrapper(run_fn)


if __name__ == "__main__":
    import typer

    typer.run(main)
