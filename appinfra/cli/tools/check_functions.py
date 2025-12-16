"""
Function size analysis tool for code quality enforcement.

Analyzes Python source files to identify functions exceeding size limits,
supporting the project's 20-30 line function size guideline.

Exit Codes:
    0: No violations found
    1: Violations found (in strict mode)
    42: Violations found but non-strict mode (warning)
"""

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from appinfra.app.tools import Tool, ToolConfig

# Exit code for "warnings but ok" - violations found in non-strict mode
EXIT_CODE_WARNING = 42


@dataclass
class FunctionInfo:
    """Information about a function."""

    name: str
    file_path: Path
    line_number: int
    end_line: int
    total_lines: int
    code_lines: int  # Excluding docstrings, comments, blank lines
    is_method: bool
    class_name: str | None


class FunctionAnalyzer:
    """AST-based function analyzer."""

    def __init__(self, limit: int = 30):
        """
        Initialize the function analyzer.

        Args:
            limit: Maximum allowed function size in lines
        """
        self.limit = limit
        self._current_class = None

    def analyze_file(self, file_path: Path) -> list[FunctionInfo]:
        """
        Analyze a single Python file.

        Args:
            file_path: Path to Python file to analyze

        Returns:
            List of FunctionInfo for functions exceeding limit
        """
        try:
            with open(file_path) as f:
                source = f.read()
            tree = ast.parse(source, filename=str(file_path))
            return self._extract_functions(tree, file_path)
        except (SyntaxError, OSError):
            # Skip files with syntax errors or read errors
            return []

    def _extract_functions(self, tree: ast.AST, file_path: Path) -> list[FunctionInfo]:
        """
        Extract function information from AST.

        Args:
            tree: Parsed AST tree
            file_path: Path to the source file

        Returns:
            List of FunctionInfo for functions exceeding limit
        """
        functions = []
        seen = set()  # Track (line_number) to avoid duplicates

        # Process top-level nodes only
        for node in tree.body:  # type: ignore[attr-defined]
            if isinstance(node, ast.ClassDef):
                # Process class methods
                self._current_class = node.name  # type: ignore[assignment]
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        info = self._analyze_function(item, file_path, is_method=True)  # type: ignore[arg-type]
                        if info and info.code_lines > self.limit:
                            key = info.line_number
                            if key not in seen:
                                seen.add(key)
                                functions.append(info)
                self._current_class = None

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Top-level function
                info = self._analyze_function(node, file_path, is_method=False)  # type: ignore[arg-type]
                if info and info.code_lines > self.limit:
                    key = info.line_number
                    if key not in seen:
                        seen.add(key)
                        functions.append(info)

        return functions

    def _is_method(self, node: ast.FunctionDef) -> bool:
        """Check if a function node is a method inside a class."""
        # This is a simple heuristic; ast.walk doesn't maintain parent info
        # In practice, we handle this by processing class bodies explicitly
        return False

    def _analyze_function(
        self, node: ast.FunctionDef, file_path: Path, is_method: bool
    ) -> FunctionInfo | None:
        """
        Analyze a single function node.

        Args:
            node: Function AST node
            file_path: Path to the source file
            is_method: Whether this is a class method

        Returns:
            FunctionInfo or None if unable to analyze
        """
        if not hasattr(node, "lineno") or not hasattr(node, "end_lineno"):
            return None

        code_lines = self._count_code_lines(node)
        total_lines = node.end_lineno - node.lineno + 1  # type: ignore[operator]

        return FunctionInfo(
            name=node.name,
            file_path=file_path,
            line_number=node.lineno,
            end_line=node.end_lineno,  # type: ignore[arg-type]
            total_lines=total_lines,
            code_lines=code_lines,
            is_method=is_method,
            class_name=self._current_class if is_method else None,
        )

    def _count_code_lines(self, node: ast.FunctionDef) -> int:
        """
        Count actual code lines, excluding docstrings.

        Args:
            node: Function AST node

        Returns:
            Number of code lines (excluding docstring)
        """
        start = node.lineno
        end = node.end_lineno

        # Subtract docstring lines if present
        if self._has_docstring(node):
            docstring_node = node.body[0]
            if hasattr(docstring_node, "end_lineno"):
                start = docstring_node.end_lineno + 1  # type: ignore[operator]

        return max(0, end - start + 1)  # type: ignore[operator]

    def _has_docstring(self, node: ast.FunctionDef) -> bool:
        """Check if function has a docstring."""
        return (
            node.body  # type: ignore[return-value]
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        )


class FunctionReporter:
    """Format and display analysis results."""

    def __init__(self, functions: list[FunctionInfo], limit: int):
        """
        Initialize the reporter.

        Args:
            functions: List of functions to report
            limit: Limit used for analysis
        """
        self.functions = functions
        self.limit = limit

    def format_simple_list(self) -> str:
        """
        Format as simple list: file:line - function - size.

        Returns:
            Formatted string output
        """
        if not self.functions:
            return "No violations found."

        lines = []
        for func in sorted(self.functions, key=lambda f: f.code_lines, reverse=True):
            location = f"{func.file_path}:{func.line_number}"
            func_name = f"{func.name}()"
            lines.append(f"{location} - {func_name} - {func.code_lines} lines")

        return "\n".join(lines)

    def format_summary_stats(self) -> str:
        """
        Format summary statistics.

        Returns:
            Formatted summary report
        """
        total = len(self.functions)

        if total == 0:
            return f"Function Size Analysis\n{'=' * 22}\nNo violations found (limit: {self.limit} lines)"

        avg_size = sum(f.code_lines for f in self.functions) / total
        largest = max(self.functions, key=lambda f: f.code_lines)

        # Build summary
        lines = [
            "Function Size Analysis",
            "=" * 22,
            f"Limit: {self.limit} lines",
            f"Violations found: {total}",
            "",
            f"Average size: {avg_size:.1f} lines",
            f"Largest function: {largest.code_lines} lines ({largest.file_path.name}:{largest.line_number} - {largest.name}())",
            "",
            f"Top {min(5, total)} largest functions:",
        ]

        sorted_funcs = sorted(self.functions, key=lambda f: f.code_lines, reverse=True)
        for i, func in enumerate(sorted_funcs[:5], 1):
            lines.append(
                f"  {i}. {func.file_path.name}:{func.line_number} - {func.name}() - {func.code_lines} lines"
            )

        return "\n".join(lines)

    def _format_critical_section(self, critical: list[FunctionInfo]) -> list[str]:
        """Format critical functions section."""
        lines = ["CRITICAL (>80 lines):"]
        for func in critical:
            lines.append(f"  ├─ {func.file_path}:{func.line_number}")
            lines.append(f"  │  └─ {func.name}() - {func.code_lines} lines")
            lines.append("  │     Recommendation: Break into focused helper functions")
            lines.append("")
        return lines

    def _format_high_priority_section(self, high: list[FunctionInfo]) -> list[str]:
        """Format high priority functions section."""
        lines = ["HIGH PRIORITY (50-80 lines):"]
        for func in high:
            lines.append(f"  ├─ {func.file_path}:{func.line_number}")
            lines.append(f"  │  └─ {func.name}() - {func.code_lines} lines")
            lines.append("  │     Recommendation: Consider extracting helper methods")
            lines.append("")
        return lines

    def _format_moderate_section(self, moderate: list[FunctionInfo]) -> list[str]:
        """Format moderate functions section."""
        lines = [f"MODERATE ({self.limit}-50 lines):"]
        for func in moderate[:5]:  # Show top 5
            lines.append(
                f"  ├─ {func.file_path}:{func.line_number} - {func.name}() - {func.code_lines} lines"
            )
        if len(moderate) > 5:
            lines.append(f"  └─ ... and {len(moderate) - 5} more")
        lines.append("")
        return lines

    def _format_summary_section(
        self,
        critical: list[FunctionInfo],
        high: list[FunctionInfo],
        moderate: list[FunctionInfo],
    ) -> list[str]:
        """Format summary section."""
        return [
            "SUMMARY:",
            f"  • {len(critical)} critical functions (>80 lines) - refactor immediately",
            f"  • {len(high)} high priority (50-80 lines) - refactor soon",
            f"  • {len(moderate)} moderate ({self.limit}-50 lines) - consider refactoring",
            "",
            "Run with --format=json for machine-readable output.",
        ]

    def format_detailed_report(self) -> str:
        """
        Format detailed report with refactoring suggestions.

        Returns:
            Formatted detailed report
        """
        if not self.functions:
            return f"Function Size Analysis - Detailed Report\n{'=' * 40}\nNo violations found (limit: {self.limit} lines)"

        total = len(self.functions)
        sorted_funcs = sorted(self.functions, key=lambda f: f.code_lines, reverse=True)

        critical = [f for f in sorted_funcs if f.code_lines > 80]
        high = [f for f in sorted_funcs if 50 < f.code_lines <= 80]
        moderate = [f for f in sorted_funcs if self.limit < f.code_lines <= 50]

        lines = [
            "Function Size Analysis - Detailed Report",
            "=" * 40,
            f"Limit: {self.limit} lines | Violations: {total}",
            "",
        ]

        if critical:
            lines.extend(self._format_critical_section(critical))
        if high:
            lines.extend(self._format_high_priority_section(high))
        if moderate:
            lines.extend(self._format_moderate_section(moderate))

        lines.extend(self._format_summary_section(critical, high, moderate))

        return "\n".join(lines)

    def format_json(self) -> str:
        """
        Format as JSON for programmatic consumption.

        Returns:
            JSON-formatted string
        """
        data = [
            {
                "file": str(func.file_path),
                "line": func.line_number,
                "name": func.name,
                "lines": func.code_lines,
                "total_lines": func.total_lines,
                "is_method": func.is_method,
                "class_name": func.class_name,
                "limit": self.limit,
            }
            for func in sorted(self.functions, key=lambda f: f.code_lines, reverse=True)
        ]
        return json.dumps(data, indent=2)


class CheckFunctionsTool(Tool):
    """Tool for checking function sizes against guidelines."""

    def __init__(self, parent: Any = None):
        """
        Initialize the check functions tool.

        Args:
            parent: Optional parent tool
        """
        config = ToolConfig(
            name="check-funcs",
            aliases=["cf"],
            help_text="Check function sizes against code quality guidelines",
            description=(
                "Analyze Python source files to identify functions exceeding "
                "size limits (default: 30 lines). Supports configurable "
                "limits, multiple output formats, and CI integration."
            ),
        )
        super().__init__(parent, config)

    def add_args(self, parser: argparse.ArgumentParser) -> None:
        """
        Add command-line arguments.

        Args:
            parser: ArgumentParser to add arguments to
        """
        self._add_dir_arg(parser)
        self._add_limit_arg(parser)
        self._add_format_arg(parser)
        self._add_strict_arg(parser)
        self._add_exclude_arg(parser)
        self._add_include_tests_arg(parser)
        self._add_sort_by_arg(parser)

    def _add_dir_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add directory argument."""
        parser.add_argument(
            "dir",
            nargs="?",
            default=".",
            help="Directory to analyze (default: current directory)",
        )

    def _add_limit_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add limit argument."""
        parser.add_argument(
            "--limit",
            "-l",
            type=int,
            default=30,
            help="Maximum function size in lines (default: 30)",
        )

    def _add_format_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add format argument."""
        parser.add_argument(
            "--format",
            "-f",
            choices=["simple", "summary", "detailed", "json"],
            default="detailed",
            help="Output format (default: detailed)",
        )

    def _add_strict_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add strict argument."""
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Exit with code 1 if violations found (for CI)",
        )

    def _add_exclude_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add exclude argument."""
        parser.add_argument(
            "--exclude",
            action="append",
            help="Patterns to exclude (can be used multiple times)",
        )

    def _add_include_tests_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add include-tests argument."""
        parser.add_argument(
            "--include-tests",
            action="store_true",
            help="Include test files (default: exclude tests)",
        )

    def _add_sort_by_arg(self, parser: argparse.ArgumentParser) -> None:
        """Add sort-by argument."""
        parser.add_argument(
            "--sort-by",
            choices=["size", "name", "file"],
            default="size",
            help="Sort results by (default: size)",
        )

    def _analyze_files(
        self, python_files: list[Path], limit: int
    ) -> list[FunctionInfo]:
        """Analyze Python files for function size violations."""
        analyzer = FunctionAnalyzer(limit)
        all_violations = []

        for file_path in python_files:
            violations = analyzer.analyze_file(file_path)
            all_violations.extend(violations)

        return all_violations

    def _print_report(
        self, reporter: FunctionReporter, output_format: str, is_quiet: bool
    ) -> None:
        """Print analysis report in specified format."""
        if is_quiet:
            return

        format_methods = {
            "simple": reporter.format_simple_list,
            "summary": reporter.format_summary_stats,
            "detailed": reporter.format_detailed_report,
            "json": reporter.format_json,
        }

        if output_format in format_methods:
            # Use stdout for clean CLI output (no log formatting)
            import sys

            sys.stdout.write(format_methods[output_format]() + "\n")

    def _log_summary(self, violation_count: int, limit: int) -> None:
        """Log analysis summary."""
        if violation_count == 0:
            self.lg.info("all functions within line limit", extra={"limit": limit})  # type: ignore[union-attr]
        else:
            self.lg.info(  # type: ignore[union-attr]
                "found functions violating the limit",
                extra={"violations": violation_count, "limit": limit},
            )

    def _get_exit_code(self, violations: list[FunctionInfo], strict: bool) -> int:
        """Determine exit code based on violation severity and strict mode."""
        if not violations:
            return 0

        if strict:
            return 1

        # Non-strict: fail on high-severity, warn on moderate-only
        has_critical = any(v.code_lines > 80 for v in violations)
        has_high = any(50 < v.code_lines <= 80 for v in violations)

        if has_critical or has_high:
            return 1  # Fail on high-severity even in non-strict

        return EXIT_CODE_WARNING  # Only moderate violations

    def run(self, **kwargs: Any) -> int:
        """
        Execute the function size checker.

        Returns:
            Exit code: 0 on success, 1 if violations found in strict mode
        """
        limit = self.args.limit
        self.lg.info(f"Checking function sizes (limit: {limit} lines)")  # type: ignore[union-attr]

        python_files = self._collect_python_files(
            [self.args.dir], self.args.exclude or [], self.args.include_tests
        )
        self.lg.debug(  # type: ignore[union-attr]
            "found Python files to analyze", extra={"files": len(python_files)}
        )

        if not python_files:
            self.lg.warning("no Python files found to analyze")  # type: ignore[union-attr]
            return 0

        all_violations = self._analyze_files(python_files, limit)
        reporter = FunctionReporter(all_violations, limit)

        self._print_report(
            reporter, self.args.format, getattr(self.args, "quiet", False)
        )
        self._log_summary(len(all_violations), limit)

        return self._get_exit_code(all_violations, self.args.strict)

    def _collect_python_files(
        self, paths: list[str], exclude_patterns: list[str], include_tests: bool
    ) -> list[Path]:
        """
        Collect all Python files to analyze.

        Args:
            paths: List of file or directory paths
            exclude_patterns: Patterns to exclude
            include_tests: Whether to include test files

        Returns:
            List of Python file paths
        """
        python_files = []

        for path_str in paths:
            path = Path(path_str)

            if not path.exists():
                self.lg.warning("path does not exist", extra={"path": path})  # type: ignore[union-attr]
                continue

            if path.is_file():
                if path.suffix == ".py":
                    if not self._should_exclude(path, exclude_patterns, include_tests):
                        python_files.append(path)
            elif path.is_dir():
                # Recursively find .py files
                for py_file in path.rglob("*.py"):
                    if not self._should_exclude(
                        py_file, exclude_patterns, include_tests
                    ):
                        python_files.append(py_file)

        return python_files

    def _should_exclude(
        self, file_path: Path, patterns: list[str], include_tests: bool
    ) -> bool:
        """
        Check if file should be excluded.

        Args:
            file_path: Path to check
            patterns: Exclusion patterns
            include_tests: Whether to include test files

        Returns:
            True if file should be excluded
        """
        file_str = str(file_path)

        # Exclude test files by default
        if not include_tests:
            if (
                "/test/" in file_str
                or "/tests/" in file_str
                or file_path.name.startswith("test_")
                or file_path.name.endswith("_test.py")
            ):
                return True

        # Check custom exclusion patterns
        for pattern in patterns:
            if file_path.match(pattern):
                return True

        return False
