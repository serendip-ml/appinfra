# Database Layer

PostgreSQL interface with connection pooling, query monitoring, and session management.

## PG (PostgreSQL)

Main PostgreSQL database interface.

```python
class PG:
    def __init__(
        self,
        config_path: str,          # Path to YAML config file
        db_name: str,              # Database config key
        readonly: bool = False     # Default read-only mode
    ): ...

    def session(self, readonly: bool | None = None) -> Session: ...
    def engine(self) -> Engine: ...
```

**Basic Usage:**

```python
from appinfra.db import PG
from appinfra.cfg import get_config_file_path
import sqlalchemy

pg = PG(get_config_file_path(), "production")

with pg.session() as session:
    result = session.execute(sqlalchemy.text("SELECT version()"))
    print(result.fetchone())
```

## Manager

Manages multiple database connections.

```python
class Manager:
    def __init__(self, config_path: str): ...

    def get_db(self, name: str) -> PG: ...
```

**Multiple Databases:**

```python
from appinfra.db import Manager
from appinfra.cfg import get_config_file_path

manager = Manager(get_config_file_path())

prod_db = manager.get_db("production")
test_db = manager.get_db("test")
```

## Configuration

Example `etc/infra.yaml`:

```yaml
databases:
  production:
    type: postgresql
    host: localhost
    port: 5432
    database: myapp_prod
    user: postgres
    password: secret
    pool_size: 10
    max_overflow: 20

  test:
    type: postgresql
    host: localhost
    port: 5432
    database: myapp_test
    user: postgres
    password: secret
```

## Read-Only Sessions

```python
from appinfra.db import PG
from appinfra.cfg import get_config_file_path

pg = PG(get_config_file_path(), "production")

# Open read-only session (no writes allowed)
with pg.session(readonly=True) as session:
    result = session.execute(sqlalchemy.text("SELECT * FROM users"))
    users = result.fetchall()
```

## Transactions

```python
from appinfra.db import PG
from appinfra.cfg import get_config_file_path
import sqlalchemy

pg = PG(get_config_file_path(), "production")

with pg.session() as session:
    try:
        session.execute(sqlalchemy.text("INSERT INTO logs (message) VALUES ('Started')"))
        session.execute(sqlalchemy.text("UPDATE status SET value = 'active'"))
        session.commit()
    except Exception:
        session.rollback()
        raise
```

## SQLAlchemy ORM

```python
from appinfra.db import PG
from appinfra.cfg import get_config_file_path
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, Integer, String

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)

pg = PG(get_config_file_path(), "production")

with pg.session() as session:
    users = session.query(User).filter(User.name == 'John').all()
```

## See Also

- [PostgreSQL Test Helper Guide](../guides/pg-test-helper.md) - Testing with databases
- [Environment Variables](../guides/environment-variables.md) - Configuration overrides
