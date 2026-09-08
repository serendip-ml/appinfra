# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""Shared status/color primitives for appinfra CLI output.

Mirrors ``appinfra/scripts/_ui.sh`` so terminal output stays consistent
whether it comes from a bash script or Python. The vocabulary is
intentionally small — one palette + five status marks — and adding a
new primitive is a design decision, not a per-caller convenience.

ANSI escapes auto-disable when the target stream is not a TTY, so the
primitives are safe to use unconditionally (pipes and log files stay
clean).
"""

from __future__ import annotations

import os
import sys
from typing import TextIO


def _ansi_enabled(stream: TextIO) -> bool:
    """ANSI on iff the stream is an interactive TTY and NO_COLOR is unset.

    Honors the widely-adopted `NO_COLOR` convention (https://no-color.org/)
    so callers redirected into pipes, log files or CI logs never receive
    escape sequences.
    """
    if os.environ.get("NO_COLOR"):
        return False
    return hasattr(stream, "isatty") and stream.isatty()


def _wrap(code: str, text: str, stream: TextIO) -> str:
    """Wrap ``text`` in an ANSI ``code`` when the stream accepts colors."""
    return f"\033[{code}m{text}\033[0m" if _ansi_enabled(stream) else text


# Palette. Callers usually reach for the mark constants below, but the
# color helpers are here for one-off inline styling that doesn't fit a mark.
def bold(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in the bold ANSI code (no-op on non-TTY streams)."""
    return _wrap("1", text, stream)


def red(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in red (no-op on non-TTY streams)."""
    return _wrap("0;31", text, stream)


def green(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in green (no-op on non-TTY streams)."""
    return _wrap("0;32", text, stream)


def yellow(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in yellow (no-op on non-TTY streams)."""
    return _wrap("0;33", text, stream)


def blue(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in blue (no-op on non-TTY streams)."""
    return _wrap("0;34", text, stream)


def cyan(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in cyan (no-op on non-TTY streams)."""
    return _wrap("0;36", text, stream)


def gray(text: str, stream: TextIO = sys.stdout) -> str:
    """Wrap ``text`` in gray (no-op on non-TTY streams)."""
    return _wrap("0;90", text, stream)


# Status marks — the canonical five. Every progress/status line in appinfra
# uses one of these; anything outside the set is a design decision.
def mark_pending(stream: TextIO = sys.stdout) -> str:
    """Gray ``[ ]`` — queued or skipped item that will not run."""
    return gray("[ ]", stream)


def mark_running(stream: TextIO = sys.stdout) -> str:
    """Yellow ``[…]`` — work in progress."""
    return yellow("[…]", stream)


def mark_ok(stream: TextIO = sys.stdout) -> str:
    """Green ``[✓]`` — successful completion."""
    return green("[✓]", stream)


def mark_warn(stream: TextIO = sys.stdout) -> str:
    """Yellow ``[⚠]`` — completed with warnings the caller should notice."""
    return yellow("[⚠]", stream)


def mark_fail(stream: TextIO = sys.stdout) -> str:
    """Red ``[✗]`` — failure the caller must act on."""
    return red("[✗]", stream)


# Convenience printers. ui_fail goes to stderr; the others to stdout.
def ui_ok(message: str, stream: TextIO = sys.stdout) -> None:
    """Print ``[✓] <message>`` to ``stream`` (stdout by default)."""
    print(f"{mark_ok(stream)} {message}", file=stream)


def ui_warn(message: str, stream: TextIO = sys.stdout) -> None:
    """Print ``[⚠] <message>`` to ``stream`` (stdout by default)."""
    print(f"{mark_warn(stream)} {message}", file=stream)


def ui_running(message: str, stream: TextIO = sys.stdout) -> None:
    """Print ``[…] <message>`` to ``stream`` (stdout by default)."""
    print(f"{mark_running(stream)} {message}", file=stream)


def ui_pending(message: str, stream: TextIO = sys.stdout) -> None:
    """Print ``[ ] <message>`` to ``stream`` (stdout by default)."""
    print(f"{mark_pending(stream)} {message}", file=stream)


def ui_fail(message: str, stream: TextIO = sys.stderr) -> None:
    """Print ``[✗] <message>`` to ``stream`` (stderr by default)."""
    print(f"{mark_fail(stream)} {message}", file=stream)
