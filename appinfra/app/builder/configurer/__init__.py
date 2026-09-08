# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: Copyright 2026 The appinfra Authors

"""
Blocks of the faceted AppBuilder, one per axis.

``ConfigConfigurer``, ``CliConfigurer``, ``ToolConfigurer``,
``LifecycleConfigurer`` and ``VersionConfigurer`` are app-only blocks.
``LoggingScope`` is the standalone ``LoggingBuilder`` bound to the AppBuilder.
"""

from .cli import CliConfigurer
from .config import ConfigConfigurer
from .lifecycle import LifecycleConfigurer
from .logging import LoggingScope
from .tool import ToolConfigurer
from .version import VersionConfigurer

__all__ = [
    "CliConfigurer",
    "ConfigConfigurer",
    "LifecycleConfigurer",
    "LoggingScope",
    "ToolConfigurer",
    "VersionConfigurer",
]
