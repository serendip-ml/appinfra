# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
CLI-surface block for AppBuilder.

Declares which standard flags the app exposes, per-flag argparse
presentation, and custom arguments. App-only concerns; there is no
standalone builder behind this block.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Self, TypedDict, Unpack

from ...core.app import DEFAULT_STANDARD_ARGS

if TYPE_CHECKING:
    from ..app import AppBuilder


class CliFlags(TypedDict, total=False):
    """Keyword form of the cli block; keys are ``DEFAULT_STANDARD_ARGS`` plus ``log``."""

    help: bool
    config_file: bool
    etc_dir: bool
    log: bool
    log_level: bool
    log_location: bool
    log_micros: bool
    log_topic: bool
    log_colors: bool
    log_json: bool
    quiet: bool
    version: bool


# ``log`` expands to every logging-related flag.
_LOG_FLAGS = frozenset(
    {
        "log_level",
        "log_location",
        "log_micros",
        "log_topic",
        "log_colors",
        "log_json",
        "quiet",
    }
)
_FLAG_NAMES = frozenset(DEFAULT_STANDARD_ARGS) | {"log"}


class CliConfigurer:
    """CLI-surface block: standard flags, per-flag presentation, custom arguments.

    Two spellings write the same state. Chained::

        AppBuilder("myapp").cli.with_flags(etc_dir=True, log=True).done()

    Keyword, returning the AppBuilder directly::

        AppBuilder("myapp").cli(etc_dir=True, log=True)

    Flags merge onto the current set, which starts as ``DEFAULT_STANDARD_ARGS``
    (only ``help`` on). ``without_flags()`` clears everything for a
    locked-down CLI. ``version=True`` exposes ``-v/--version`` with the text
    of the ``.version`` block at build time.
    """

    def __init__(self, app_builder: AppBuilder):
        """Bind the block to its parent builder."""
        self._app_builder = app_builder

    def with_flags(self, **flags: Unpack[CliFlags]) -> Self:
        """Enable or disable standard flags by name.

        ``log`` expands to every log flag; an explicit key wins over the
        alias.

        Raises:
            ValueError: for no flags, an unknown name, or a non-boolean value.
        """
        if not flags:
            raise ValueError(
                "with_flags() needs at least one flag; log=True covers every log flag"
            )
        standard_args = self._app_builder._standard_args
        resolved: dict[str, Any] = dict(flags)
        if "log" in resolved:
            log_value = resolved.pop("log")
            _check_bool("log", log_value)
            for name in _LOG_FLAGS:
                resolved.setdefault(name, log_value)
        for name, enabled in resolved.items():
            _check_flag_name(name)
            _check_bool(name, enabled)
            standard_args[name] = enabled
        return self

    def without_flags(self) -> Self:
        """Disable every standard flag, ``help`` included."""
        for key in self._app_builder._standard_args:
            self._app_builder._standard_args[key] = False
        return self

    def with_flag(self, name: str, **presentation: Any) -> Self:
        """Override the argparse presentation of one standard flag.

        Presentation means ``help``, ``metavar``, ``choices`` and the like.
        ``default`` is rejected: a default is a value, and values come from
        the subsystem block or the config file. ``dest`` is rejected because
        the framework reads parsed args by a fixed attribute name. Does not
        enable the flag; see ``with_flags``.

        Raises:
            ValueError: for an unknown or aliased name, or a rejected key.
        """
        _check_flag_name(name)
        if name == "log":
            raise ValueError("'log' is an alias; name a specific log flag")
        if name == "help":
            raise ValueError("'help' has no presentation to override")
        for key in ("default", "dest"):
            if key in presentation:
                raise ValueError(f"with_flag({name!r}) does not accept {key!r}")
        overrides = self._app_builder._standard_arg_overrides
        overrides.setdefault(name, {}).update(presentation)
        return self

    def with_argument(self, *args: Any, **kwargs: Any) -> Self:
        """Add a custom argument; arguments are those of ``parser.add_argument``."""
        self._app_builder._custom_args.append((args, kwargs))
        return self

    def done(self) -> AppBuilder:
        """Return to the AppBuilder."""
        return self._app_builder

    def __call__(self, **flags: Unpack[CliFlags]) -> AppBuilder:
        """Keyword form of the block; same arguments as ``with_flags``."""
        self.with_flags(**flags)
        return self._app_builder


def _check_flag_name(name: str) -> None:
    """Reject names outside the standard-flag set and the ``log`` alias."""
    if name not in _FLAG_NAMES:
        raise ValueError(
            f"Unknown CLI flag: {name!r}. Valid flags: {', '.join(sorted(_FLAG_NAMES))}"
        )


def _check_bool(name: str, value: Any) -> None:
    """Reject non-boolean flag values."""
    if not isinstance(value, bool):
        raise ValueError(
            f"Value for {name!r} must be a boolean, got {type(value).__name__}"
        )
