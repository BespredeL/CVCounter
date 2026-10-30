# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Website: https://bespredel.name

"""In-memory ledger of what a counter has seen, saved and still owes the user."""

from __future__ import annotations


class CountState:
    """
    Totals, current-batch totals and pending keyboard corrections of one counter.

    The numbers are kept in the order the UI and the database expect: ``total_count``
    is every object ever crossed the line, ``current_count`` the batch since the last
    partial reset, and defect/correct adjustments accumulate separately.
    """

    def __init__(self) -> None:
        self.total_count: int = 0
        self.current_count: int = 0
        self.defect_count: int = 0
        self.correct_count: int = 0
        self.pending_defect_count: int = 0
        self.pending_correct_count: int = 0
        self.class_counts: dict[int, int] = {}
        self.current_class_counts: dict[int, int] = {}

    def increment_class_count(self, class_id: int) -> None:
        """Raise both the lifetime and the current-batch counter of one class."""
        key = int(class_id)
        self.class_counts[key] = self.class_counts.get(key, 0) + 1
        self.current_class_counts[key] = self.current_class_counts.get(key, 0) + 1

    def set_pending(self, pending_defect: int, pending_correct: int) -> None:
        """Store unsaved keyboard corrections; defects never go negative."""
        self.pending_defect_count = max(int(pending_defect), 0)
        self.pending_correct_count = int(pending_correct)

    def clear_pending(self) -> None:
        """Forget the keyboard corrections, e.g. right after they were saved."""
        self.pending_defect_count = 0
        self.pending_correct_count = 0

    def resolve_adjustment(self, correct_count: int | None, defect_count: int | None) -> tuple[int, int]:
        """
        Return the ``(correct, defect)`` to apply, falling back to the pending values.

        A zero or missing argument means "use what the operator typed", not "no change".
        """
        defect = int(defect_count if defect_count is not None and defect_count != 0 else self.pending_defect_count)
        correct = int(
            correct_count if correct_count is not None and correct_count != 0 else self.pending_correct_count)
        return correct, defect

    def apply_save(self, correct_count: int, defect_count: int) -> str:
        """
        Fold an adjustment into the totals and return the database's total string.

        Args:
            correct_count (int): Already resolved correct count.
            defect_count (int): Already resolved defect count.

        Returns:
            str: ``total - defect + correct`` after the adjustment was applied.
        """
        self.defect_count += defect_count
        self.correct_count += correct_count
        self.current_count = self.current_count - defect_count + correct_count
        return str(self.total_count - self.defect_count + self.correct_count)

    def apply_current_reset(self, correct_count: int, defect_count: int) -> None:
        """Keep the lifetime total, restart the current batch with an adjustment."""
        self.current_count = 0
        self.current_class_counts.clear()
        self.defect_count += defect_count
        self.correct_count += correct_count

    def reset_counts(self) -> None:
        """Zero every accumulated number and both per-class maps."""
        self.total_count = 0
        self.current_count = 0
        self.defect_count = 0
        self.correct_count = 0
        self.class_counts.clear()
        self.current_class_counts.clear()
