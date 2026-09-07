# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Logging block for AppBuilder.

``LoggingScope`` is the standalone ``LoggingBuilder`` bound to an
``AppBuilder``: every builder method is inherited, so nothing is
re-declared, and ``done()`` folds what was set into the app's
programmatic config layer under ``logging``. The app's lifecycle builds
the root logger from that layer merged with the config file and the CLI
flags, so a display option left untouched here keeps the file's value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, TypedDict, Unpack

from ....log.builder.builder import LoggingBuilder
from ....log.logger import Logger
from .block import check_fields
from .config import ConfigConfigurer

if TYPE_CHECKING:
    from ..app import AppBuilder


class LoggingFields(TypedDict, total=False):
    """Keyword form of the logging block; see ``LoggingScope.__call__``."""

    level: str | int
    location: bool | int
    micros: bool
    colors: bool
    location_color: str
    topic_levels: dict[str, str]
    runtime_updates: bool


_OPTION_KEYS = frozenset({"level", "location", "micros", "colors", "location_color"})


class LoggingScope(LoggingBuilder):
    """Logging block: the standalone builder, scoped to an AppBuilder.

    Chained::

        AppBuilder("myapp").logging.with_level("debug").with_location(2).done()

    Keyword, returning the AppBuilder directly::

        AppBuilder("myapp").logging(level="debug", location=2)

    Handlers and extra fields added here reach the app's root logger
    through ``logging.handlers`` and ``logging.extra`` in the programmatic
    layer. ``build()`` raises: the app's lifecycle builds the logger; close
    the block with ``done()``. ``done()`` is the only fold, so a later
    ``.config`` write to the same key wins; a block left open with unfolded
    changes fails at ``AppBuilder.build()``.
    """

    block = "logging"

    def __init__(self, app_builder: AppBuilder):
        """Bind the block to its parent builder."""
        super().__init__(app_builder._name or "app")
        self._app_builder = app_builder
        self._folded: dict[str, Any] = {}

    def with_runtime_updates(self, enabled: bool = True) -> Self:
        """Apply later topic-level changes to loggers that already exist.

        Off by default: topic levels then apply only to loggers created
        afterwards. Enable before the app creates its loggers.
        """
        from ....log.level_manager import LogLevelManager

        manager = LogLevelManager.get_instance()
        if enabled:
            manager.enable_runtime_updates()
        else:
            manager.disable_runtime_updates()
        return self

    def build(self) -> Logger:
        """Not available on the scope; the app's lifecycle builds the logger."""
        raise TypeError(
            "LoggingScope does not build a logger; close the block with done() "
            "and let the app build it"
        )

    def done(self) -> AppBuilder:
        """Fold what was set into the programmatic layer and return to the AppBuilder."""
        self._apply()
        self._app_builder._close(self)
        return self._app_builder

    def _apply(self) -> None:
        """Write explicit options, handlers and extra into ``logging``. Idempotent."""
        values = self._values()
        if values:
            # Direct construction: the property would open the config block
            # while this block is the open one.
            ConfigConfigurer(self._app_builder).with_overrides({"logging": values})
        self._folded = values

    def _pending(self) -> bool:
        """True when something was set after the last ``done()``."""
        return self._values() != self._folded

    def _values(self) -> dict[str, Any]:
        """The ``logging`` section the block currently describes."""
        values: dict[str, Any] = {
            name: getattr(self, f"_{name}") for name in sorted(self._explicit)
        }
        handlers = self._serialized_handlers()
        if handlers:
            values["handlers"] = handlers
        if self._extra:
            values["extra"] = dict(self._extra)
        return values

    def _serialized_handlers(self) -> dict[str, dict[str, Any]]:
        """Handlers as ``logging.handlers`` entries, keyed ``builder_<position>``.

        The prefix says where the entry came from and keeps it clear of the
        names a config file would use, since the fold deep-merges with them.
        """
        handlers: dict[str, dict[str, Any]] = {}
        for index, handler in enumerate(self._handlers):
            try:
                handlers[f"builder_{index}"] = handler.to_dict()
            except NotImplementedError as e:
                raise ValueError(
                    f"{type(handler).__name__} cannot be expressed as config, so "
                    "the logging block cannot carry it; add it to the root "
                    "logger from a startup hook instead"
                ) from e
        return handlers

    def __call__(self, **fields: Unpack[LoggingFields]) -> AppBuilder:
        """Keyword form of the block; returns the AppBuilder."""
        check_fields("logging", fields, LoggingFields.__annotations__)
        self.with_options({k: v for k, v in fields.items() if k in _OPTION_KEYS})
        if "topic_levels" in fields:
            self.with_topic_levels(fields["topic_levels"])
        if "runtime_updates" in fields:
            self.with_runtime_updates(fields["runtime_updates"])
        return self.done()
