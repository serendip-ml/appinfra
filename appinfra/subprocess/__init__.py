"""Subprocess infrastructure for child processes.

This module provides utilities for subprocess lifecycle management,
including signal handling, config hot-reload, and graceful shutdown.
"""

from .context import SubprocessContext

__all__ = ["SubprocessContext"]
