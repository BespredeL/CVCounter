# -*- coding: utf-8 -*-
# ! python3

# Developed for CVCounterWEB
# Compatibility shim: redirects legacy Sort tracker to the improved BYTETracker.
# Removed legacy unused imports (matplotlib, scikit-image, MOT benchmark CLI).

from __future__ import annotations

from system.core.byte_tracker import BYTETracker


class Sort(BYTETracker):
    """
    Backwards compatibility wrapper for legacy Sort tracker interface.
    Powered by ByteTrack under the hood for higher accuracy and fewer ID switches.
    """
    def __init__(
            self,
            max_age: int = 30,
            min_hits: int = 3,
            iou_threshold: float = 0.3,
            **kwargs,
    ):
        super().__init__(
            track_thresh=0.45,
            match_thresh=max(0.5, 1.0 - float(iou_threshold)),
            max_age=max_age,
            min_hits=min_hits,
            **kwargs,
        )


__all__ = ['Sort', 'BYTETracker']
