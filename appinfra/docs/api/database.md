---
title: Database Layer
keywords:
  - database
  - postgresql
  - postgres
  - connection pool
  - session
  - sqlalchemy
  - query
  - PG class
  - pgserver
  - image
  - docker image
  - pgvector
  - timescaledb
  - postgis
  - extensions
  - create extension
  - dbs
aliases:
  - db-api
  - postgres-api
---

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

Database connections are configured in `etc/infra.yaml` under the `dbs` key.

```yaml
dbs:
  main:
    url: "postgresql://postgres:secret@localhost:5432/myapp"
    pool_size: 10              # Connection pool size (default: 5)
    max_overflow: 20           # Max overflow connections (default: 10)
    create_db: true            # Create database if not exists (default: false)
    extensions:                # PostgreSQL extensions to create
      - vector
      - pg_trgm

  readonly:
    url: "postgresql://postgres:secret@localhost:5432/myapp"
    readonly: true             # Read-only mode (default: false)
```

### Database Configuration Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `url` | string | required | PostgreSQL connection URL |
| `pool_size` | int | 5 | Connection pool size |
| `max_overflow` | int | 10 | Max overflow connections |
| `pool_timeout` | int | 30 | Pool timeout in seconds |
| `pool_recycle` | int | 3600 | Connection recycle time in seconds |
| `pool_pre_ping` | bool | true | Enable connection health checks |
| `readonly` | bool | false | Read-only mode |
| `create_db` | bool | false | Create database if not exists |
| `extensions` | list | [] | PostgreSQL extensions to create |

### PostgreSQL Extensions (`extensions` field)

The `extensions` field specifies PostgreSQL extensions to create automatically when `pg.migrate()`
is called. Extensions are created using `CREATE EXTENSION IF NOT EXISTS`.

```yaml
dbs:
  main:
    url: "postgresql://localhost/myapp"
    create_db: true
    extensions:
      - vector         # pgvector for embeddings
      - pg_trgm        # Trigram similarity for fuzzy search
      - postgis        # Geospatial support
```

**How it works:**
1. Extensions are created during `pg.migrate()`, before table creation
2. Uses `CREATE EXTENSION IF NOT EXISTS` (safe to run multiple times)
3. Extension names must match pattern: lowercase letters, numbers, underscores, hyphens
   (e.g., `vector`, `pg_trgm`, `pg-cron`)

**Important:** The PostgreSQL server must have the extension binaries installed. Use a custom
Docker image (via `pgserver.image`) that includes the extensions you need.

### Server-Level vs Database-Level Extensions

Some extensions require configuration at both levels:

| Level | Config Location | Purpose |
|-------|-----------------|---------|
| Server | `pgserver.postgres_conf.shared_preload_libraries` | Extensions loaded at server startup |
| Database | `dbs.<name>.extensions` | Extensions created per database |

**Extensions requiring both levels (examples):** `timescaledb`, `pg_cron`, `pg_stat_statements`,
`pgaudit`, `auto_explain`

```yaml
# Server config (pg.yaml)
pgserver:
  image: timescale/timescaledb:latest-pg16
  postgres_conf:
    shared_preload_libraries:
      - timescaledb              # Must be preloaded at server startup

# Database config (infra.yaml)
dbs:
  main:
    url: "postgresql://localhost/myapp"
    extensions:
      - timescaledb              # Also needs CREATE EXTENSION per database
```

**Extensions needing only database-level (examples):** `vector`, `pg_trgm`, `postgis`, `uuid-ossp`

## PostgreSQL Server Configuration (pg.yaml)

Defines the Docker-based PostgreSQL server for local development.

```yaml
pgserver:
  version: 16                      # PostgreSQL version (required unless image is specified)
  name: infra-pg                   # Server name/identifier
  port: 7432                       # PostgreSQL port
  user: postgres                   # Database user
  pass: ''                         # Database password
  image: pgvector/pgvector:pg16   # Optional: custom Docker image
```

### Custom Docker Image (`image` field)

Use the `image` field to run PostgreSQL with extensions like pgvector, TimescaleDB, or PostGIS.

**Either `version` or `image` must be specified:**

| Configuration | Use Case | Image Used |
|---------------|----------|------------|
| `version` only | Standard PostgreSQL | `postgres:VERSION` |
| `image` only | Custom image with extensions | Your specified image |
| Both | Custom image with explicit version for documentation | Your specified image |

**Examples:**

```yaml
# Standard PostgreSQL 16
pgserver:
  version: 16
  name: my-pg
  port: 5432

# pgvector for vector similarity search
pgserver:
  name: learn-pg
  port: 5432
  image: pgvector/pgvector:pg16

# TimescaleDB for time-series data
pgserver:
  name: timeseries-pg
  port: 5432
  image: timescale/timescaledb:latest-pg16

# PostGIS for geospatial data
pgserver:
  name: geo-pg
  port: 5432
  image: postgis/postgis:16-3.4
```

**Important:** The custom image must be PostgreSQL-compatible (based on the official `postgres`
image). Images that extend the official postgres image work correctly:

- `pgvector/pgvector:pg16` - Vector similarity search
- `timescale/timescaledb:latest-pg16` - Time-series database
- `postgis/postgis:16-3.4` - Geospatial database

Non-PostgreSQL databases or heavily modified images will fail to start because the framework passes
PostgreSQL-specific CLI arguments to the container.

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
