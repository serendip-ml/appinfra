# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""What every AppBuilder block shares: a name, a ``done()``, and the keyword check."""

import inspect
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

_BUILDER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Block(Protocol):
    """A block of the AppBuilder: opened by a property, closed by ``done()``."""

    block: str

    def done(self) -> Any:
        """Close the block and return to the AppBuilder."""
        ...


@dataclass(frozen=True)
class OpenBlock:
    """The block currently open on an AppBuilder and where it was opened."""

    block: Block
    where: str

    @property
    def name(self) -> str:
        """The block's name, for messages."""
        return self.block.block


def caller_location() -> str:
    """``file:line`` of the nearest frame outside the builder package."""
    frame = inspect.currentframe()
    while frame is not None and frame.f_code.co_filename.startswith(_BUILDER_DIR):
        frame = frame.f_back
    if frame is None:
        return "<unknown>"
    return f"{frame.f_code.co_filename}:{frame.f_lineno}"


def check_fields(block: str, fields: Mapping[str, Any], allowed: Iterable[str]) -> None:
    """Reject keyword-form keys that are not fields of the block.

    ``Unpack[TypedDict]`` only guards under a type checker; at runtime
    ``**fields`` accepts anything, and a misspelled key would otherwise be
    dropped without a signal.

    Raises:
        TypeError: naming every key outside ``allowed``.
    """
    unknown = set(fields) - set(allowed)
    if unknown:
        raise TypeError(f"unknown {block} field(s): {', '.join(sorted(unknown))}")
