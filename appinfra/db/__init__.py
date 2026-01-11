"""
Database management module for handling multiple database connections.

This module provides a database manager that can handle multiple database
connections of different types, supporting PostgreSQL and SQLite.
"""

from .db import Manager, UnknownDBTypeException
from .pg import PG, Interface
from .sqlite import SQLite
from .utils import detach, detach_all

__all__ = [
    "Manager",
    "UnknownDBTypeException",
    "PG",
    "SQLite",
    "Interface",
    "detach",
    "detach_all",
]
