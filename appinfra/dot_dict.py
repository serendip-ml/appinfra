"""
Dictionary-like object implementation with nested structure support.

This module provides DotDict, a class that behaves like a dictionary but allows
attribute-style access and supports nested dictionary/object structures with
dot-notation path traversal.
"""

import builtins
import datetime
from collections.abc import ItemsView, KeysView, ValuesView
from typing import Any

from . import time as timeutils
from .dict import DictInterface


class DotDict(DictInterface):
    """
    Dictionary-like object with attribute-style access and nested structure support.

    Provides a convenient way to work with configuration data and other structured
    information using both dictionary-style and attribute-style access patterns.
    Supports automatic conversion of nested dictionaries to DotDict instances.
    """

    # Keys that would shadow critical methods and are not allowed.
    # Only includes methods that are commonly called (dict, to_dict, set, clear, get, has).
    # Excludes dict-like methods (keys, values, items) since these are common config keys
    # and users typically access config data as attributes, not by calling these methods.
    _RESERVED_KEYS = frozenset(
        {
            "set",
            "clear",
            "dict",
            "to_dict",
            "get",
            "has",
        }
    )

    def __init__(self, **kwargs: Any) -> None:
        """
        Initialize DotDict with initial key-value pairs.

        Args:
            **kwargs: Initial key-value pairs to set
        """
        self.set(**kwargs)

    def set(self, **kwargs: Any) -> "DotDict":
        """
        Set multiple key-value pairs, with automatic nested object creation.

        Args:
            **kwargs: Key-value pairs to set

        Returns:
            self: For method chaining
        """
        for key, val in kwargs.items():
            self._set_item(key, val)
        return self

    def _set_item(self, key: Any, val: Any) -> None:
        """
        Set a single key-value pair with automatic nested object creation.

        Args:
            key: Key to set (will be converted to string if needed)
            val: Value to set

        Raises:
            ValueError: If key would shadow a method name
        """
        # Convert date keys to strings
        if isinstance(key, datetime.date):
            key = timeutils.date_to_str(key)
        elif not isinstance(key, str):
            # Convert non-string keys to strings
            key = str(key)

        # Prevent shadowing methods
        if key in self._RESERVED_KEYS:
            raise ValueError(
                f"Key '{key}' is reserved and cannot be used (would shadow method)"
            )

        # Handle nested dictionaries
        if isinstance(val, dict):
            setattr(self, key, DotDict(**val))
        # Handle lists with potential nested structures
        elif isinstance(val, list):
            setattr(self, key, list(map(self._map_entry, val)))
        # Handle simple values
        else:
            setattr(self, key, val)

    def clear(self) -> None:
        """
        Clear all attributes from the object.
        """
        keys = [k for k in self.__dict__.keys()]
        for k in keys:
            delattr(self, k)

    @staticmethod
    def _map_entry(entry: Any) -> Any:
        """
        Map a list entry to appropriate object type.

        Args:
            entry: Entry to map

        Returns:
            DotDict or original entry: Mapped entry
        """
        if isinstance(entry, dict):
            return DotDict(**entry)
        return entry

    def dict(self) -> dict[str, Any]:
        """
        Convert the object to a dictionary representation.

        Returns:
            dict: Dictionary representation with nested DotDict instances converted
        """
        result = {}
        for key, val in self.__dict__.items():
            result[key] = val.dict() if isinstance(val, DotDict) else val
        return result

    def to_dict(self) -> builtins.dict[str, Any]:
        """
        Recursively convert DotDict and all nested structures to plain dicts.

        Handles nested DotDicts, lists containing DotDicts, and other structures.

        Returns:
            dict: Fully converted dictionary with no DotDict instances
        """
        result: dict[str, Any] = {}
        for key, val in self.__dict__.items():
            if isinstance(val, DotDict):
                result[key] = val.to_dict()
            elif isinstance(val, list):
                result[key] = [
                    item.to_dict() if isinstance(item, DotDict) else item
                    for item in val
                ]
            elif isinstance(val, dict):
                # Handle plain dicts that might contain DotDicts
                result[key] = {
                    k: v.to_dict() if isinstance(v, DotDict) else v
                    for k, v in val.items()
                }
            else:
                result[key] = val
        return result

    def keys(self) -> KeysView[str]:
        """
        Get all keys in the object.

        Returns:
            dict_keys: Object keys
        """
        return self.__dict__.keys()

    def values(self) -> ValuesView[Any]:
        """
        Get all values in the object.

        Returns:
            dict_values: Object values
        """
        return self.__dict__.values()

    def items(self) -> ItemsView[str, Any]:
        """
        Get all key-value pairs in the object.

        Returns:
            dict_items: Object key-value pairs
        """
        return self.__dict__.items()

    def __contains__(self, key: Any) -> bool:
        """
        Check if key exists in the object.

        Args:
            key: Key to check

        Returns:
            bool: True if key exists
        """
        return key in self.__dict__

    def __getitem__(self, key: str) -> Any:
        """
        Get value by key with dictionary-style access.

        Args:
            key: Key to get

        Returns:
            Value or None: Object value or None if key doesn't exist
        """
        return getattr(self, key) if key in self.__dict__ else None

    def __setitem__(self, key: str, val: Any) -> None:
        """
        Set value by key with dictionary-style access.

        Args:
            key: Key to set
            val: Value to set
        """
        if key in self.__dict__:
            delattr(self, key)
        self._set_item(key, val)

    def __len__(self) -> int:
        """
        Get the length of the object.

        Returns:
            int: Number of items in the object
        """
        return len(self.dict())

    def __str__(self) -> str:
        """
        Get string representation of the object.

        Returns:
            str: String representation of the object as a dictionary
        """
        return str(self.dict())

    def has(self, path: str) -> bool:
        """
        Check if a dot-separated path exists in the object.

        Args:
            path (str): Dot-separated path to check (e.g., "database.host")

        Returns:
            bool: True if the path exists
        """
        if not path:
            return False

        cur = self.__dict__
        for item in path.split("."):
            if not item:  # Skip empty components
                continue
            if not isinstance(cur, dict) or item not in cur:
                return False
            cur = cur[item]
            # If cur is a DotDict, get its __dict__ for next iteration
            if hasattr(cur, "__dict__"):
                cur = cur.__dict__
        return True

    def get(self, path: str, default: Any = None, max_steps_up: int = 0) -> Any:
        """
        Get value by dot-separated path with fallback support.

        Follows standard dict.get() semantics: returns default (None) if path not found.

        Args:
            path (str): Dot-separated path to get (e.g., "database.host")
            default: Default value to return if path not found (default: None)
            max_steps_up (int): Maximum number of steps up the hierarchy to search

        Returns:
            Value: Found value or default
        """
        if not path:
            return default

        cur = self.__dict__
        history = []
        components = [
            item for item in path.split(".") if item
        ]  # Filter empty components

        for i, item in enumerate(components):
            if isinstance(cur, dict) and item in cur:
                history.append(cur)
                cur = cur[item]
                # If cur is a DotDict, get its __dict__ for next iteration
                if hasattr(cur, "__dict__") and i < len(components) - 1:
                    cur = cur.__dict__
                if i == len(components) - 1:
                    return cur
            elif i == len(components) - 1:
                # Try searching up the hierarchy
                for j in range(min(max_steps_up, len(history))):
                    if isinstance(history[-j - 1], dict) and item in history[-j - 1]:
                        return history[-j - 1][item]
            else:
                break
        return default


class DotDictPathNotFoundError(Exception):
    """
    Exception raised when a path is not found in a DotDict.

    Attributes:
        obj: The DotDict instance where the path was not found
        path: The path that was not found
    """

    def __init__(self, obj: DotDict, path: str) -> None:
        """
        Initialize the path not found error.

        Args:
            obj: DotDict instance
            path (str): Path that was not found
        """
        self.obj = obj
        self.path = path
