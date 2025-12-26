"""
Logger classes for the logging system.

This module provides enhanced logger classes with custom functionality,
including custom log levels, callback support, and multiprocessing features.
"""

import collections
import logging
import sys
import threading
from typing import Any

from .callback import CallbackRegistry
from .config import ChildLogConfig, LogConfig
from .config_holder import LogConfigHolder
from .constants import LogConstants

# Type alias for config parameter that can be either type
ConfigLike = LogConfig | ChildLogConfig


class Logger(logging.Logger):
    """
    Enhanced logger with custom record creation and callback support.

    Extends the standard Python logger with:
    - Custom record creation for extra field handling
    - Callback system for log event processing
    - Location tracking configuration
    - Microsecond timestamp support
    - Custom trace and trace2 methods
    """

    def __init__(
        self,
        name: str,
        config: ConfigLike | None = None,
        callback_registry: CallbackRegistry | None = None,
        extra: dict[str, Any] | collections.OrderedDict | None = None,
        suppress_format_errors: bool = False,
    ):
        """
        Initialize the enhanced logger.

        Args:
            name: Logger name
            config: Logger configuration (LogConfig for root, ChildLogConfig for children).
                    Will create default LogConfig if None.
            callback_registry: Callback registry for this logger (optional, will create default if None)
            extra: Pre-populated extra fields to include in all log records
            suppress_format_errors: If True, silently skip format errors (for SQLAlchemy
                                    integration). If False (default), log format errors to stderr.
        """
        # Handle case where Logger is instantiated by standard logging system
        if config is None:
            config = LogConfig.from_params("info", location=0, micros=False)
        if callback_registry is None:
            callback_registry = CallbackRegistry()

        # Handle disabled logging (level = False)
        if config.level is False:
            # Set to highest possible level to disable all logging
            super().__init__(name, logging.CRITICAL + 1)
            self._logging_disabled = True
        else:
            super().__init__(name, config.level)
            self._logging_disabled = False

        self._config = config
        self._holder: LogConfigHolder | None = None  # Set by factory for hot-reload
        self._callbacks = callback_registry
        self._extra = extra or {}
        self._root_logger: Logger | None = None  # Set for derived "view" loggers
        self._suppress_format_errors = suppress_format_errors
        # Thread-safe storage for caller traces, keyed by thread ID
        self._pending_traces: dict[int, tuple[list[str], list[int]]] = {}

        # Override makeRecord to handle extra fields
        self._original_makeRecord = self.makeRecord
        self.makeRecord = self._makeRecord  # type: ignore[assignment,method-assign]

    @property
    def config(self) -> ConfigLike:
        """Get logger configuration (LogConfig for root, ChildLogConfig for children)."""
        return self._config

    @property
    def location(self) -> int:
        """Get location display level from holder (supports hot-reload).

        The holder is shared with root logger, so updates propagate immediately.
        """
        if self._holder:
            return self._holder.location
        # Fallback for loggers created without holder
        return getattr(self._config, "location", 0)

    @property
    def micros(self) -> bool:
        """Get microsecond precision from holder (supports hot-reload).

        The holder is shared with root logger, so updates propagate immediately.
        """
        if self._holder:
            return self._holder.micros
        # Fallback for loggers created without holder
        return getattr(self._config, "micros", False)

    @property
    def disabled(self) -> bool:
        """Check if logging is disabled."""
        return self._logging_disabled

    @disabled.setter
    def disabled(self, value: bool) -> None:
        """Set the disabled state."""
        self._logging_disabled = value

    def get_level(self) -> int | bool:
        """Get current log level."""
        return self._config.level

    def isEnabledFor(self, level: int) -> bool:
        """Check if enabled, respecting ancestor loggers' levels.

        Walks up the parent chain to ensure all ancestors would also allow
        logging at this level. This enables hot-reload of log levels - when
        a parent's level changes, all descendants immediately respect it.

        Only walks up the parent chain for loggers created by our factory
        (those with _root_logger attribute set), not for plain Python loggers.
        """
        if not super().isEnabledFor(level):
            return False

        # Only check parent if it's one of our loggers (has _root_logger attribute)
        # This avoids interference when Logger class is used by plain logging.getLogger()
        if self.parent and hasattr(self.parent, "_root_logger"):
            return self.parent.isEnabledFor(level)

        return True

    def setLevel(self, level: int | str) -> None:
        """Set level and clear this logger's cache.

        Overrides base setLevel to explicitly clear our cache. Python's
        Manager._clear_cache() only clears loggers in loggerDict, but our
        custom logger hierarchy may not be registered there.
        """
        super().setLevel(level)
        # Explicitly clear our own cache since we may not be in loggerDict
        self._cache.clear()  # type: ignore[attr-defined]

    def _merge_extra(
        self, extra: dict[str, Any] | collections.OrderedDict | None
    ) -> dict[str, Any] | collections.OrderedDict:
        """Merge pre-populated extra fields with per-call extra fields."""
        # Use OrderedDict if either source is OrderedDict to preserve key ordering
        merged: dict[str, Any] | collections.OrderedDict
        if isinstance(self._extra, collections.OrderedDict) or isinstance(
            extra, collections.OrderedDict
        ):
            merged = collections.OrderedDict(self._extra)
        else:
            merged = self._extra.copy()
        if extra:
            merged.update(extra)
        return merged

    def _attach_infra_attrs(
        self, record: logging.LogRecord, merged_extra: dict[str, Any]
    ) -> None:
        """Attach __infra__ prefixed attributes to record."""
        # Use setattr to avoid Python name mangling with __ prefix
        setattr(record, "__infra__extra", merged_extra)

        # Read and remove trace from instance storage (set by findCaller)
        # Keyed by thread ID for thread safety
        pending_trace = self._pending_traces.pop(threading.get_ident(), None)
        if pending_trace is not None:
            pathnames, linenos = pending_trace
            setattr(record, "__infra__pathnames", pathnames)
            setattr(record, "__infra__linenos", linenos)

    def _makeRecord(
        self,
        name: str,
        level: int,
        fn: str,
        lno: int,
        msg: str,
        args: tuple,
        exc_info: Any | None,
        func: str | None = None,
        extra: dict[str, Any] | collections.OrderedDict | None = None,
        sinfo: str | None = None,
    ) -> logging.LogRecord:
        """Create log record with extra field handling."""
        merged_extra = self._merge_extra(extra)
        record = self._original_makeRecord(
            name,
            level,
            fn,
            lno,
            msg,
            args,
            exc_info,
            func=func,
            extra=merged_extra,
            sinfo=sinfo,
        )
        self._attach_infra_attrs(record, merged_extra)
        return record

    def trace(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        Log a TRACE level message.

        Args:
            msg: Log message
            *args: Message format arguments
            **kwargs: Additional keyword arguments including 'extra' for structured data
        """
        if self._logging_disabled:
            return
        trace_level = LogConstants.CUSTOM_LEVELS["TRACE"]
        if self.isEnabledFor(trace_level):
            self._log(trace_level, msg, args, **kwargs)

    def trace2(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """
        Log a TRACE2 level message (most verbose level).

        Args:
            msg: Log message
            *args: Message format arguments
            **kwargs: Additional keyword arguments including 'extra' for structured data
        """
        if self._logging_disabled:
            return
        trace2_level = LogConstants.CUSTOM_LEVELS["TRACE2"]
        if self.isEnabledFor(trace2_level):
            self._log(trace2_level, msg, args, **kwargs)

    def _log(self, level: int, msg: str, args: tuple, **kwargs: Any) -> None:  # type: ignore[override]
        """Enhanced logging with callback support."""
        if self._logging_disabled:
            return

        try:
            super()._log(level, msg, args, **kwargs)
        except (TypeError, ValueError) as e:
            # Format string errors (e.g., wrong number of args, type mismatch)
            if self._suppress_format_errors:
                # Silently skip for SQLAlchemy integration where format errors are expected
                pass
            else:
                # Log to stderr so format bugs don't go unnoticed
                msg_preview = msg[:80] + "..." if len(msg) > 80 else msg
                sys.stderr.write(
                    f"LOG_FORMAT_ERROR [{self.name}]: {e.__class__.__name__}: {e} "
                    f"| msg={msg_preview!r} args={args!r}\n"
                )
        except Exception as e:
            # Only report unexpected errors
            sys.stderr.write(f"CRITICAL: Logger failed - unable to log {msg}: {e}\n")

        self._callbacks.trigger(level, self, msg, args, kwargs)

    def is_logged(self, level: int) -> bool:
        """Check if a level would be logged."""
        if self._logging_disabled:
            return False
        return level >= self.level

    def callHandlers(self, record: logging.LogRecord) -> None:
        """
        Pass a record to all relevant handlers.

        For derived "view" loggers (those with _root_logger set), delegate to
        the root logger's handlers instead of using our own. This allows derived
        loggers to share handlers with the root without duplicating them.
        """
        if self._root_logger is not None:
            # Derived logger - use root's handlers
            for handler in self._root_logger.handlers:
                if record.levelno >= handler.level:
                    handler.handle(record)
        else:
            # Root logger - standard behavior
            super().callHandlers(record)

    def findCaller(
        self, stack_info: bool = False, stacklevel: int = 1
    ) -> tuple[str, int, str, str | None]:
        """
        Override to support multiple caller tracking while returning standard types.

        Returns standard (pathname, lineno, funcname, sinfo) for compatibility with
        external formatters. Full trace is stored in _pending_traces (keyed by thread ID)
        and attached to the record in _makeRecord as __infra__pathnames and __infra__linenos.
        """
        from types import FrameType

        f: FrameType | None = logging.currentframe()
        while f is not None and f.f_code is not None:
            fname = f.f_code.co_filename
            if fname == logging.__file__ or fname == __file__:
                f = f.f_back
            else:
                break

        if f is None:
            return "(unknown file)", 0, "(unknown function)", None

        files, linenos = self._trace_callers(f)
        # Store full trace keyed by thread ID for thread-safe access in _makeRecord
        self._pending_traces[threading.get_ident()] = (files, linenos)
        # Return standard types (first element) for external formatter compatibility
        return files[0], linenos[0], f.f_code.co_name, None

    def _trace_callers(self, f: Any) -> tuple[list[str], list[int]]:
        """Trace multiple callers for location display."""
        linenos = [f.f_lineno]
        files = [f.f_code.co_filename]

        while len(files) < self.location:
            f = f.f_back
            if f is None or f.f_code is None:
                break

            name = f.f_code.co_filename
            if "site-packages" in name or "/usr/lib" in name:
                continue

            linenos.append(f.f_lineno)
            files.append(f.f_code.co_filename)

        return files, linenos
