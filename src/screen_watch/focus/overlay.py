"""Interactive flash overlay for loose region selection (tkinter)."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from dataclasses import dataclass
from typing import Any

from screen_watch.focus.region import BBox, normalize_bbox
from screen_watch.focus.virtual_screen import virtual_screen_geometry

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RegionGesture:
    """Raw user gesture from the overlay (screen coordinates)."""

    bbox: BBox
    cancelled: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "x": self.bbox.x,
            "y": self.bbox.y,
            "width": self.bbox.width,
            "height": self.bbox.height,
            "cancelled": self.cancelled,
        }


def _apply_windows_layered(root: tk.Tk) -> None:
    """Mark the overlay as a tool window (no taskbar); still receives input while visible."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        GWL_EXSTYLE = -20
        WS_EX_TOOLWINDOW = 0x00000080
        WS_EX_LAYERED = 0x00080000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_LAYERED | WS_EX_TOOLWINDOW
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
    except Exception:
        logger.debug("Could not apply Win32 layered styles", exc_info=True)


def select_region_interactive(
    title: str = "screen-watch — drag a loose region, Esc to cancel",
    *,
    accept_on_release: bool = True,
) -> RegionGesture:
    """
    Show a short-lived fullscreen overlay; user drags a rectangle.

    While visible the overlay captures input (required to draw the box). It is
    not permanently click-through — that would prevent selecting. Esc cancels.
    On mouse release, accepts by default (Enter also accepts).
    """
    root = tk.Tk()
    root.title(title)
    root.attributes("-topmost", True)
    try:
        root.attributes("-alpha", 0.30)
    except tk.TclError:
        pass
    root.configure(bg="#0d0d0d")
    root.overrideredirect(True)

    vs = virtual_screen_geometry(
        fallback_width=root.winfo_screenwidth(),
        fallback_height=root.winfo_screenheight(),
    )
    sw, sh = vs.width, vs.height
    root.geometry(f"{sw}x{sh}+{vs.left}+{vs.top}")
    root.update_idletasks()
    _apply_windows_layered(root)

    canvas = tk.Canvas(root, cursor="crosshair", bg="#0d0d0d", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)
    hint = canvas.create_text(
        sw // 2,
        36,
        text="Drag loose box · release to accept · Esc cancel · covers all monitors",
        fill="#f2f2f2",
        font=("Segoe UI", 13),
    )

    state: dict[str, Any] = {"start": None, "rect": None, "bbox": None, "cancelled": False}

    def finish(cancel: bool = False) -> None:
        state["cancelled"] = cancel
        root.quit()

    def on_press(event: tk.Event) -> None:  # type: ignore[type-arg]
        state["start"] = (event.x_root, event.y_root)
        if state["rect"] is not None:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(
            event.x, event.y, event.x, event.y, outline="#00e5a8", width=2
        )

    def on_drag(event: tk.Event) -> None:  # type: ignore[type-arg]
        if state["start"] is None or state["rect"] is None:
            return
        x0, y0 = state["start"]
        canvas.coords(
            state["rect"],
            x0 - root.winfo_rootx(),
            y0 - root.winfo_rooty(),
            event.x_root - root.winfo_rootx(),
            event.y_root - root.winfo_rooty(),
        )

    def on_release(event: tk.Event) -> None:  # type: ignore[type-arg]
        if state["start"] is None:
            return
        x0, y0 = state["start"]
        state["bbox"] = normalize_bbox(x0, y0, event.x_root, event.y_root)
        if accept_on_release and state["bbox"].width > 2 and state["bbox"].height > 2:
            finish(cancel=False)

    def on_key(event: tk.Event) -> None:  # type: ignore[type-arg]
        if event.keysym == "Escape":
            finish(cancel=True)
        elif event.keysym in {"Return", "KP_Enter"}:
            finish(cancel=False)

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    root.bind("<Key>", on_key)
    # Brief flash of hint emphasis
    root.after(900, lambda: canvas.itemconfigure(hint, fill="#b0b0b0"))

    root.focus_force()
    root.mainloop()
    try:
        root.destroy()
    except tk.TclError:
        pass

    if state["cancelled"] or state["bbox"] is None:
        return RegionGesture(bbox=BBox(0, 0, 1, 1), cancelled=True)
    return RegionGesture(bbox=state["bbox"], cancelled=False)


def gesture_json(gesture: RegionGesture) -> str:
    import json

    return json.dumps(gesture.as_dict())
