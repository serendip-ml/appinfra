# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Blocks of the faceted AppBuilder, one per axis.

``ConfigConfigurer``, ``CliConfigurer``, ``ToolConfigurer``,
``LifecycleConfigurer`` and ``VersionConfigurer`` are app-only blocks.
``LoggingScope`` and ``ServerScope`` are the standalone ``LoggingBuilder``
and FastAPI ``ServerBuilder`` bound to the AppBuilder.
"""

from .cli import CliConfigurer
from .config import ConfigConfigurer
from .lifecycle import LifecycleConfigurer
from .logging import LoggingScope
from .tool import ToolConfigurer
from .version import VersionConfigurer

# ServerScope is not re-exported: its module pulls in the FastAPI runtime,
# which only apps that declare .server should pay for. Import it from
# appinfra.app.builder.configurer.server.
__all__ = [
    "CliConfigurer",
    "ConfigConfigurer",
    "LifecycleConfigurer",
    "LoggingScope",
    "ToolConfigurer",
    "VersionConfigurer",
]
