from importlib.metadata import PackageNotFoundError, version

from . import db, net
from .app.cfg import (
    DEFAULT_CONFIG_FILE,
    ETC_DIR,
    PROJECT_ROOT,
    Config,
    get_config_path,
    get_default_config,
    get_etc_dir,
    get_project_root,
)
from .deprecation import deprecated
from .dict import DictInterface
from .dot_dict import DotDict
from .ewma import EWMA
from .exceptions import (
    ConfigError,
    DatabaseError,
    InfraError,
    LoggingError,
    ObservabilityError,
    ServerError,
    ToolError,
    ValidationError,
)
from .rate_limit import RateLimiter
from .regex_utils import (
    RegexComplexityError,
    RegexTimeoutError,
    safe_compile,
    safe_findall,
    safe_match,
    safe_search,
)
from .utils import is_int, pretty

# Version is read from package metadata (pyproject.toml)
try:
    __version__ = version("appinfra")
except PackageNotFoundError:
    # Package not installed, use fallback (development mode)
    __version__ = "0.1.0-dev"

# Explicit public API
__all__ = [
    # Version
    "__version__",
    # Modules
    "db",
    "net",
    # Core classes
    "DictInterface",
    "DotDict",
    "EWMA",
    "RateLimiter",
    "Config",
    # Config utilities
    "get_project_root",
    "get_etc_dir",
    "get_config_path",
    "get_default_config",
    "PROJECT_ROOT",
    "ETC_DIR",
    "DEFAULT_CONFIG_FILE",
    # Utils
    "pretty",
    "is_int",
    # Deprecation
    "deprecated",
    # Exceptions
    "InfraError",
    "ConfigError",
    "DatabaseError",
    "LoggingError",
    "ValidationError",
    "ToolError",
    "ServerError",
    "ObservabilityError",
    # Regex utilities (ReDoS protection)
    "safe_compile",
    "safe_match",
    "safe_search",
    "safe_findall",
    "RegexTimeoutError",
    "RegexComplexityError",
]
