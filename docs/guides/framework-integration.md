# Framework Integration Guide

This guide explains how to integrate the appinfra Makefile framework into downstream projects,
particularly when using appinfra as a Git submodule.

## Quick Start

```makefile
# Minimal submodule integration
infra := submodules/infra

# Configure your project
INFRA_DEV_PKG_NAME := myproject

# Include framework (config must be first)
include $(infra)/scripts/make/Makefile.config
include $(infra)/scripts/make/Makefile.env
include $(infra)/scripts/make/Makefile.help
include $(infra)/scripts/make/Makefile.utils
include $(infra)/scripts/make/Makefile.dev
include $(infra)/scripts/make/Makefile.pytest
include $(infra)/scripts/make/Makefile.clean
```

## Include Order

**Critical:** Include order matters. Always follow this sequence:

```makefile
# 1. REQUIRED FIRST - Handles config loading and deprecation
include $(infra)/scripts/make/Makefile.config

# 2. Core modules (order matters)
include $(infra)/scripts/make/Makefile.env      # Python detection
include $(infra)/scripts/make/Makefile.help     # Help system
include $(infra)/scripts/make/Makefile.utils    # Utilities (areyousure, etc.)

# 3. Feature modules (order flexible)
include $(infra)/scripts/make/Makefile.dev      # Requires: env, utils
include $(infra)/scripts/make/Makefile.pytest   # Requires: env
include $(infra)/scripts/make/Makefile.docs     # Requires: env
include $(infra)/scripts/make/Makefile.pg       # Requires: env, utils
include $(infra)/scripts/make/Makefile.cicd     # Standalone
include $(infra)/scripts/make/Makefile.clean    # Requires: utils
```

Or use `Makefile.all` to include everything in the correct order:

```makefile
include $(infra)/scripts/make/Makefile.all
```

## Variable Precedence

Variables are resolved in this order (highest to lowest priority):

1. **Environment variables** - `INFRA_DEV_PKG_NAME=foo make test`
2. **Makefile variables before include** - `INFRA_DEV_PKG_NAME := foo`
3. **Makefile.local** - Optional overrides file (not committed)
4. **Framework defaults** - Defined in `Makefile.config`

### Example: Setting Package Name

```makefile
# In Makefile (before include)
INFRA_DEV_PKG_NAME := myproject
include $(infra)/scripts/make/Makefile.all

# Or via environment variable (for CI/testing)
# INFRA_DEV_PKG_NAME=myproject make test.coverage
```

## Common Configuration

### Minimal Configuration

```makefile
# Makefile
INFRA_DEV_PKG_NAME := myproject

infra := submodules/infra
include $(infra)/scripts/make/Makefile.all
```

### Full Configuration

```makefile
# Makefile
INFRA_DEV_PKG_NAME := myproject
INFRA_DEV_CQ_STRICT := true
INFRA_PYTEST_TESTS_DIR := tests
INFRA_DOCS_CONFIG := etc/mkdocs.yaml

# Hide unused features
INFRA_DISABLE_GROUPS := pg. cicd.

infra := submodules/infra
include $(infra)/scripts/make/Makefile.all
```

## Extending Targets

Use double-colon rules (`::`) to extend framework targets:

```makefile
include $(infra)/scripts/make/Makefile.all

# Extend cleanup
clean::
	@echo "* cleaning app-specific files..."
	@rm -rf .app-cache/

# Extend tests
test.integration::
	@echo "* running app integration tests..."
	@./scripts/test-api.sh

# Extend linting
lint::
	@./scripts/check-schemas.sh
```

## Running check.sh

The `check.sh` script is designed to be run via Make, not directly:

```bash
# Correct - uses exported variables from Makefile
make check
make check.raw      # For CI logs
make check.summary  # Summaries only

# Incorrect - will use fallback defaults (INFRA_DEV_PKG_NAME=appinfra)
./scripts/check.sh
```

## Handling Empty Test Directories

The framework handles pytest exit code 5 (no tests collected) gracefully. Running `make test.unit`
on a project without unit tests will succeed silently rather than failing.

This allows downstream projects to include the full test framework even if they don't have all
test categories implemented yet.

## Troubleshooting

### Variable Not Taking Effect

**Cause:** Setting variable after include.

```makefile
# Wrong - too late
include $(infra)/scripts/make/Makefile.all
INFRA_DEV_PKG_NAME := myproject

# Correct - before include
INFRA_DEV_PKG_NAME := myproject
include $(infra)/scripts/make/Makefile.all
```

### Include Order Errors

**Cause:** Including modules before their dependencies.

```makefile
# Wrong - dev requires env and utils
include $(infra)/scripts/make/Makefile.dev
include $(infra)/scripts/make/Makefile.env

# Correct - use Makefile.all or follow documented order
include $(infra)/scripts/make/Makefile.all
```

### check.sh Uses Wrong Package Name

**Cause:** Running check.sh directly instead of via Make.

**Solution:** Always use `make check`, which exports the correct variables.

## Example: Complete Submodule Integration

```
myproject/
├── Makefile
├── submodules/
│   └── infra/  (git submodule)
├── myproject/
│   └── __init__.py
└── tests/
    └── test_example.py
```

```makefile
# Makefile
INFRA_DEV_PKG_NAME := myproject
INFRA_DISABLE_GROUPS := pg. cicd.

infra := submodules/infra
include $(infra)/scripts/make/Makefile.all

##@ Application

run:  ## Run the application
	@$(PYTHON) -m myproject
```

## See Also

- [Makefile Customization Guide](makefile-customization.md) - Detailed variable reference
- [Test Naming Standards](test-naming-standards.md) - Test organization
