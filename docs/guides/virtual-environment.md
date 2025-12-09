# Virtual Environment Setup

This project uses a virtual environment at `~/.venv` for all Python operations.

## Quick Setup

```bash
# Install dependencies
make setup

# Activate manually (optional - Makefile does this automatically)
source ~/.venv/bin/activate
```

## Usage

All `make` targets automatically use the virtual environment:
```bash
make test.unit
make test.integration
make fmt
```

## Direct Python Usage

```bash
# Use venv Python directly
~/.venv/bin/python script.py

# Or activate manually
source ~/.venv/bin/activate
python script.py
deactivate
```

## Benefits

- **Isolated dependencies** - No conflicts with system Python
- **Reproducible** - Consistent environment across machines
- **Automatic** - Makefile handles activation

## Running Scripts Directly

Scripts use the portable shebang `#!/usr/bin/env python3`. To make `python3` resolve to your
venv, choose one of these options:

### Option A: Permanent (recommended)

Add to `~/.bashrc` or `~/.zshrc`:

```bash
export PATH="$HOME/.venv/bin:$PATH"
```

Then reload: `source ~/.bashrc`

### Option B: Per-session (activate venv)

```bash
source ~/.venv/bin/activate
./examples/01_basics/hello_world.py  # Now works - python3 resolves to venv
deactivate  # When done
```

### Option C: Per-project with direnv

Create `.envrc` in project root:

```bash
export PATH="$HOME/.venv/bin:$PATH"
```

Then: `direnv allow`
