"""Pan/zoom camera wrapper.

Holds the current viewport and converts between screen and world coordinates.
The editor view drives this; everything in the canvas is rendered through it.
"""

from __future__ import annotations

import arcade


MIN_ZOOM = 0.25
MAX_ZOOM = 4.0


class Camera:
    def __init__(self, window: arcade.Window) -> None:
        self.window = window
        self.cam = arcade.Camera2D()
        self.zoom: float = 1.0
        self.cx: float = window.width / 2
        self.cy: float = window.height / 2
        self._apply()

    def _apply(self) -> None:
        self.cam.position = (self.cx, self.cy)
        self.cam.zoom = self.zoom

    def use(self) -> None:
        """Activate this camera for subsequent draw calls."""
        self.cam.use()

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        """Convert a window-space pixel to world coordinates."""
        # Camera2D centers (cx,cy) at the screen's middle. So a screen point
        # offset (sx - W/2, sy - H/2) maps to a world offset divided by zoom.
        wx = self.cx + (sx - self.window.width / 2) / self.zoom
        wy = self.cy + (sy - self.window.height / 2) / self.zoom
        return wx, wy

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        sx = self.window.width / 2 + (wx - self.cx) * self.zoom
        sy = self.window.height / 2 + (wy - self.cy) * self.zoom
        return sx, sy

    def pan(self, dx_screen: float, dy_screen: float) -> None:
        # dx_screen positive = mouse moved right; world moves left under cursor.
        self.cx -= dx_screen / self.zoom
        self.cy -= dy_screen / self.zoom
        self._apply()

    def zoom_at(self, sx: float, sy: float, factor: float) -> None:
        """Zoom toward a screen point (keeps that world-point under cursor)."""
        new_zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        if new_zoom == self.zoom:
            return
        # Anchor: world point under cursor must remain under cursor after zoom.
        wx_before, wy_before = self.screen_to_world(sx, sy)
        self.zoom = new_zoom
        self._apply()
        wx_after, wy_after = self.screen_to_world(sx, sy)
        self.cx += wx_before - wx_after
        self.cy += wy_before - wy_after
        self._apply()

    def reset(self) -> None:
        self.zoom = 1.0
        self.cx = self.window.width / 2
        self.cy = self.window.height / 2
        self._apply()
