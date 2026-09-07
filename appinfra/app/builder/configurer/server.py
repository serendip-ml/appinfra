# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Server block for AppBuilder.

``ServerScope`` is the standalone FastAPI ``ServerBuilder`` bound to an
``AppBuilder``: every builder method and facet (``.routes``,
``.subprocess``, ``.uvicorn``) is inherited. ``AppBuilder.build()``
registers a ``ServerPlugin`` for the scope, which builds the server after
the other plugins have added their routes and middleware, and adds the
``serve`` tool. Serving requires the ``fastapi`` extra.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, TypedDict, Unpack

from ....log.logger import Logger
from ...fastapi.builder.server import ServerBuilder
from ...fastapi.runtime.server import Server
from .block import check_fields

if TYPE_CHECKING:
    from ..app import AppBuilder


class ServerFields(TypedDict, total=False):
    """Keyword form of the server block; see ``ServerScope.__call__``."""

    host: str
    port: int
    title: str
    description: str
    version: str
    timeout: float
    uvicorn: Mapping[str, Any]


class ServerScope(ServerBuilder):
    """Server block: the standalone FastAPI builder, scoped to an AppBuilder.

    Chained::

        (AppBuilder("myapp")
            .server.with_port(8080)
                .routes.with_route("/health", health).done()
                .done()
            .build())

    Keyword, returning the AppBuilder directly::

        AppBuilder("myapp").server(port=8080, uvicorn={"workers": 4})

    ``build()`` raises: the AppBuilder builds the server; close the block
    with ``done()``.
    """

    block = "server"

    def __init__(self, app_builder: AppBuilder):
        """Bind the block to its parent builder."""
        name = app_builder._name or "server"
        super().__init__(lg=Logger(name), name=name)
        self._app_builder = app_builder

    def done(self) -> AppBuilder:
        """Return to the AppBuilder."""
        self._app_builder._close(self)
        return self._app_builder

    def build(self) -> Server:
        """Not available on the scope; the AppBuilder builds the server."""
        raise TypeError(
            "ServerScope does not build the server; close the block with done() "
            "and let the AppBuilder build it"
        )

    def __call__(self, **fields: Unpack[ServerFields]) -> AppBuilder:
        """Keyword form of the block; ``uvicorn`` takes ``UvicornFields``."""
        check_fields("server", fields, ServerFields.__annotations__)
        setters: dict[str, Any] = {
            "host": self.with_host,
            "port": self.with_port,
            "title": self.with_title,
            "description": self.with_description,
            "version": self.with_version,
            "timeout": self.with_timeout,
        }
        uvicorn = fields.get("uvicorn")
        if uvicorn is not None:
            self.uvicorn(**uvicorn)
        for key, value in fields.items():
            if key != "uvicorn":
                setters[key](value)
        return self.done()
