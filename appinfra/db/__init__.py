"""
Database management module for handling multiple database connections.

This module provides a database manager that can handle multiple database
connections of different types, currently supporting PostgreSQL.
"""

from .db import Manager, UnknownDBTypeException
from .pg import PG, Interface

__all__ = ["Manager", "UnknownDBTypeException", "PG", "Interface"]
