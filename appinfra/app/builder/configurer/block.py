# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""What every AppBuilder block shares: a name, a ``done()``, and the keyword check."""

import inspect
import os
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

_BUILDER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Block(Protocol):
    """A block of the AppBuilder: opened by a property, closed by ``done()``."""

    block_name: str

    def done(self) -> object:
        """Close the block and return to the AppBuilder."""
        ...


class BlockOwner(Protocol):
    """What opens and closes blocks: the AppBuilder."""

    def _close(self, block: Block) -> None:
        """Close ``block`` if it is the open one."""
        ...


@contextmanager
def close_on_error(owner: BlockOwner, block: Block) -> Iterator[None]:
    """Close ``block`` if the body raises.

    The keyword forms validate before ``done()`` runs; without this a
    rejected call would leave the block open, and the next block access on
    the same builder would fail for a line that already failed.
    """
    try:
        yield
    except BaseException:
        owner._close(block)
        raise


@dataclass(frozen=True)
class OpenBlock:
    """The block currently open on an AppBuilder and where it was opened."""

    block: Block
    where: str

    @property
    def name(self) -> str:
        """The block's name, for messages."""
        return self.block.block_name


def caller_location() -> str:
    """``file:line`` of the nearest frame outside the builder package."""
    frame = inspect.currentframe()
    while frame is not None and frame.f_code.co_filename.startswith(
        _BUILDER_DIR + os.sep
    ):
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
