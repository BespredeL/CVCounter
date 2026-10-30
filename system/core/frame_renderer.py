# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""Drawing of counting zones, track indicators and the FPS overlay onto a frame."""

from __future__ import annotations

from collections.abc import Callable

import cv2
import numpy as np

from system.core.count_kernel import build_zone_mask
from system.core.counter_config import CounterSettings
from system.core.label_render import get_label_font, render_cached_badge
from system.utils.counting_area import DEFAULT_COUNTING_AREA_COLOR, DIRECTION_VECTORS


class FrameRenderer:
    """
    Turns a raw frame into the picture the browser sees.

    Read-only with respect to the counting state: the caller tells it which track
    ids were already counted, and the zone geometry comes from the counter's
    settings, so changing a zone through those settings invalidates the mask here.
    """

    POLYGON_ALPHA: float = 0.4
    FPS_POSITION: tuple = (20, 70)
    FPS_FONT_SCALE: float = 1.5
    FPS_COLOR: tuple = (0, 0, 255)
    FPS_THICKNESS: int = 2

    def __init__(
            self,
            settings: CounterSettings,
            label_for: Callable[[int], str],
            fps_provider: Callable[[], float],
    ) -> None:
        """
        Args:
            settings (CounterSettings): Live configuration; read on every draw call.
            label_for (Callable[[int], str]): Human-readable name of a class id.
            fps_provider (Callable[[], float]): Current camera FPS of the stream.
        """
        self.settings = settings
        self.label_for = label_for
        self.fps_provider = fps_provider
        self._mask: np.ndarray | None = None
        self._cam_fps = 0.0

    @property
    def zones(self) -> list:
        """Counting zones, falling back to the legacy single polygon."""
        return self.settings.counting_areas or [{
            'points': self.settings.counting_area,
            'color': self.settings.counting_area_color,
            'direction': self.settings.counting_area_direction,
        }]

    @property
    def mask(self) -> np.ndarray | None:
        """Zone-index mask built for the last frame shape, or None when unknown."""
        return self._mask

    def invalidate_zones(self) -> None:
        """Forget the cached mask after the zones changed."""
        self._mask = None

    def ensure_mask(self, frame_shape: tuple[int, int]) -> None:
        """
        Build the point-in-polygon mask once per frame size.

        Args:
            frame_shape (tuple[int, int]): Height and width of the frame.

        Returns:
            None
        """
        if self._mask is not None:
            return

        self._mask = build_zone_mask(frame_shape, self.zones)

    def draw_zones(self, image: np.ndarray, scale: float = 1.0) -> np.ndarray:
        """
        Draws all counting zones on the given image.

        Args:
            image (numpy.ndarray): The image on which the counting area should be drawn.
            scale (float): Multiply zone points when the image was already resized.

        Returns:
            numpy.ndarray: The image with the counting area drawn on it.
        """
        overlay = image.copy()
        fallback_color = self.settings.counting_area_color or DEFAULT_COUNTING_AREA_COLOR

        for zone in self.zones:
            points = zone.get('points') or []
            if len(points) < 3:
                continue
            pts = np.asarray(points, dtype=np.float32)
            if scale != 1.0:
                pts = pts * scale
            pts = pts.astype(np.int32).reshape((-1, 1, 2))
            color = tuple(zone.get('color') or fallback_color)
            cv2.fillPoly(overlay, [pts], color)

            # Draw directional arrow on zone if configured
            direction = zone.get('direction', 'any')
            if direction != 'any':
                M = cv2.moments(pts)
                if M['m00'] != 0:
                    mcx = int(M['m10'] / M['m00'])
                    mcy = int(M['m01'] / M['m00'])
                else:
                    mcx = int(np.mean(pts[:, 0, 0]))
                    mcy = int(np.mean(pts[:, 0, 1]))

                arrow_len = 35 if scale == 1.0 else max(12, int(35 * scale))
                vec = DIRECTION_VECTORS.get(direction)
                if vec:
                    ux, uy = vec
                    p1 = (int(mcx - arrow_len * ux), int(mcy - arrow_len * uy))
                    p2 = (int(mcx + arrow_len * ux), int(mcy + arrow_len * uy))
                    cv2.arrowedLine(overlay, p1, p2, (0, 0, 0), 4, tipLength=0.35, line_type=cv2.LINE_AA)
                    cv2.arrowedLine(overlay, p1, p2, (255, 255, 255), 2, tipLength=0.35, line_type=cv2.LINE_AA)

        return cv2.addWeighted(overlay, self.POLYGON_ALPHA, image, 1 - self.POLYGON_ALPHA, 0)

    def draw_indicator(
            self,
            image: np.ndarray,
            center: tuple[int, int],
            rid: int,
            counted: bool = False,
            box: tuple[int, int, int, int] | None = None,
            class_id: int = -1,
            scale: float = 1.0,
    ) -> None:
        """
        Draws an indicator on the given image (in place).

        Args:
            image (numpy.ndarray): The image on which the indicator should be drawn.
            center (tuple[int, int]): The center coordinates of the indicator.
            rid (int): The ID of the indicator.
            counted (bool): Whether this track already crossed the counting zone.
            box (tuple[int, int, int, int], optional): (x1, y1, x2, y2) bounding box.
            class_id (int, optional): The class ID of the object.
            scale (float): Multiply coordinates when the image was already resized.

        Returns:
            None
        """
        settings = self.settings
        if scale != 1.0:
            center = (int(center[0] * scale), int(center[1] * scale))
            if box is not None:
                box = tuple(int(value * scale) for value in box)

        color = settings.indicator_counted_color if counted else settings.indicator_detected_color
        indicator_size = settings.indicator_size if scale == 1.0 else max(
            2, int(round(settings.indicator_size * scale)))

        if settings.indicator_mode == 'box' and box is not None:
            x1, y1, x2, y2 = box
            # Draw bounding box rectangle
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2 if scale == 1.0 else 1)

            # Center tracking dot (subtle, so users see the point triggering the counting zone)
            dot_radius = max(2, min(indicator_size // 2, 6))
            cv2.circle(image, center, dot_radius, color, cv2.FILLED)

            # Prepare text badge: Class name + track ID
            cls_name = self.label_for(class_id)
            label = f"{cls_name} #{rid}" if rid is not None and rid >= 0 else cls_name

            font = get_label_font(13)
            img_h, img_w = image.shape[:2]

            if font is not None:
                badge = render_cached_badge(label, color, font)
                badge_h, badge_w = badge.shape[:2]

                badge_x1 = max(0, min(x1, img_w - badge_w))
                badge_x2 = min(img_w, badge_x1 + badge_w)

                if y1 - badge_h >= 0:
                    badge_y1 = y1 - badge_h
                    badge_y2 = y1
                else:
                    badge_y1 = min(img_h - 1, max(0, y1))
                    badge_y2 = min(img_h, badge_y1 + badge_h)

                bw = badge_x2 - badge_x1
                bh = badge_y2 - badge_y1

                if bw > 0 and bh > 0:
                    image[badge_y1:badge_y2, badge_x1:badge_x2] = badge[:bh, :bw]
            else:
                (text_w, text_h), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                badge_h = text_h + baseline + 4
                badge_y1 = max(0, y1 - badge_h) if y1 - badge_h >= 0 else min(img_h - badge_h, y1)
                badge_y2 = badge_y1 + badge_h
                badge_x2 = min(img_w, x1 + text_w + 6)
                cv2.rectangle(image, (x1, badge_y1), (badge_x2, badge_y2), color, cv2.FILLED)
                cv2.putText(image, label, (x1 + 3, badge_y2 - baseline - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0),
                            1, cv2.LINE_AA)
        else:
            cv2.circle(image, center, indicator_size, color, cv2.FILLED)

    def draw_fps_hud(self, image: np.ndarray, out_fps: float, inf_ms: float) -> None:
        """
        Draw camera FPS, output FPS, and inference time in the top-left corner.

        Shown when general.show_fps is enabled. Drawn on the frame that is encoded
        for the browser.

        Args:
            image (numpy.ndarray): Frame to draw onto.
            out_fps (float): FPS of the frames handed to the browser.
            inf_ms (float): Smoothed inference time in milliseconds.

        Returns:
            None
        """
        if not self.settings.show_fps or image is None or image.size == 0:
            return
        try:
            self._cam_fps = float(self.fps_provider())
        except Exception:
            pass

        height, width = image.shape[:2]
        panel_w, panel_h = 188, 84
        if width < panel_w + 24 or height < panel_h + 24:
            return
        x, y = 16, 16
        roi = image[y:y + panel_h, x:x + panel_w]
        tint = np.empty_like(roi)
        tint[:] = (28, 30, 34)
        cv2.addWeighted(tint, 0.82, roi, 0.18, 0, roi)
        cv2.rectangle(image, (x, y), (x + panel_w - 1, y + panel_h - 1), (90, 96, 104), 1, cv2.LINE_AA)

        rows = (
            ("CAM", f"{self._cam_fps:4.1f}", "fps"),
            ("OUT", f"{out_fps:4.1f}", "fps"),
            ("INF", f"{inf_ms:4.1f}", "ms"),
        )
        font = cv2.FONT_HERSHEY_SIMPLEX
        for index, (label, value, unit) in enumerate(rows):
            baseline = y + 24 + index * 24
            cv2.putText(image, label, (x + 12, baseline), font, 0.52, (168, 174, 182), 1, cv2.LINE_AA)
            cv2.putText(image, value, (x + 68, baseline), font, 0.58, (248, 248, 248), 1, cv2.LINE_AA)
            cv2.putText(image, unit, (x + 138, baseline), font, 0.42, (148, 154, 162), 1, cv2.LINE_AA)

    def draw_debug_fps(self, image: np.ndarray, fps: int) -> None:
        """
        Draw the plain debug FPS text used when the HUD is off.

        Args:
            image (numpy.ndarray): Frame to draw onto.
            fps (int): Whole frames per second of the processing loop.

        Returns:
            None
        """
        cv2.putText(image, f'FPS: {fps}', self.FPS_POSITION, cv2.FONT_HERSHEY_SIMPLEX,
                    self.FPS_FONT_SCALE, self.FPS_COLOR, self.FPS_THICKNESS)
