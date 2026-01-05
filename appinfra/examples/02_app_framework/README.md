# App Framework

Application architecture patterns using the infra framework.

## Learning Progression

Follow this order to understand application patterns:

1. **app_with_commands.py** - Command-based apps
2. **app_with_tool.py** - Tool-based apps
3. **app_with_subtools.py** - Tool groups and hierarchies
4. **app_with_tool_builders.py** - Builder-based tool creation
5. **app_with_ticker.py** - Background task execution

## Examples

### app_with_commands.py
Command-based application structure.

**What you'll learn:**
- Command pattern for CLI applications
- Argument parsing
- Command registration

**Run:**
```bash
~/.venv/bin/python examples/02_app_framework/app_with_commands.py
```

---

### app_with_tool.py
Tool-based application with single tool.

**What you'll learn:**
- Tool pattern for modular applications
- Tool registration
- Tool execution

**Run:**
```bash
~/.venv/bin/python examples/02_app_framework/app_with_tool.py
```

---

### app_with_subtools.py
Tool groups and hierarchical tool structure.

**What you'll learn:**
- Creating tool groups
- Subtool organization
- Tool hierarchies

**Run:**
```bash
~/.venv/bin/python examples/02_app_framework/app_with_subtools.py
```

---

### app_with_tool_builders.py
Builder-based tool creation without classes.

**What you'll learn:**
- Creating tools with builders instead of classes
- Functional approach to tool definition
- Simpler tool creation for small tools

**Run:**
```bash
~/.venv/bin/python examples/02_app_framework/app_with_tool_builders.py
```

---

### app_with_ticker.py
Application with background task execution.

**What you'll learn:**
- Ticker for periodic tasks
- Background task scheduling
- Combining app framework with time utilities

**Run:**
```bash
~/.venv/bin/python examples/02_app_framework/app_with_ticker.py
```

**Key concepts:**
- `Ticker` class from `infra.time`
- Periodic execution
- Scheduled vs continuous modes

---

## Architecture Patterns

### Command Pattern
Best for: CLI applications with multiple commands (git-like interfaces)
- Each command is a separate handler
- Clean argument parsing
- Easy to extend

### Tool Pattern
Best for: Modular applications with discrete features
- Tools can be registered/unregistered dynamically
- Tool groups for organization
- Better for larger applications

### Builder Pattern
Best for: Simple tools without boilerplate
- Less code than class-based tools
- Good for small, focused tools
- Functional style

## Next Steps

- [Logging](../03_logging/) - Add logging to your apps
- [Configuration](../04_configuration/) - Configure your apps
- [Advanced](../06_advanced/) - Advanced patterns

## Related Documentation

- [Main README](../README.md) - Full examples index
