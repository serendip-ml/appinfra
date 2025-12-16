"""
Tests for app/tools/check_functions.py.

Tests key functionality including:
- FunctionInfo dataclass
- FunctionAnalyzer AST-based analysis
- FunctionReporter output formatting
- CheckFunctionsTool CLI integration
- File collection and filtering logic
"""

import json
import tempfile
from pathlib import Path
from textwrap import dedent
from unittest.mock import Mock

import pytest

from appinfra.cli.tools.check_functions import (
    EXIT_CODE_WARNING,
    CheckFunctionsTool,
    FunctionAnalyzer,
    FunctionInfo,
    FunctionReporter,
)

# =============================================================================
# Test FunctionInfo Dataclass
# =============================================================================


@pytest.mark.unit
class TestFunctionInfo:
    """Test FunctionInfo dataclass."""

    def test_function_info_creation(self):
        """Test FunctionInfo can be created with all fields."""
        info = FunctionInfo(
            name="my_function",
            file_path=Path("/path/to/file.py"),
            line_number=10,
            end_line=50,
            total_lines=41,
            code_lines=35,
            is_method=False,
            class_name=None,
        )

        assert info.name == "my_function"
        assert info.file_path == Path("/path/to/file.py")
        assert info.line_number == 10
        assert info.end_line == 50
        assert info.total_lines == 41
        assert info.code_lines == 35
        assert info.is_method is False
        assert info.class_name is None

    def test_method_info_with_class_name(self):
        """Test FunctionInfo for a method includes class_name."""
        info = FunctionInfo(
            name="my_method",
            file_path=Path("/path/to/file.py"),
            line_number=20,
            end_line=60,
            total_lines=41,
            code_lines=35,
            is_method=True,
            class_name="MyClass",
        )

        assert info.is_method is True
        assert info.class_name == "MyClass"


# =============================================================================
# Test FunctionAnalyzer
# =============================================================================


@pytest.mark.unit
class TestFunctionAnalyzerInit:
    """Test FunctionAnalyzer initialization."""

    def test_default_threshold(self):
        """Test analyzer initializes with default threshold of 30."""
        analyzer = FunctionAnalyzer()

        assert analyzer.limit == 30
        assert analyzer._current_class is None

    def test_custom_threshold(self):
        """Test analyzer accepts custom threshold."""
        analyzer = FunctionAnalyzer(limit=50)

        assert analyzer.limit == 50


@pytest.mark.unit
class TestFunctionAnalyzerAnalyzeFile:
    """Test FunctionAnalyzer.analyze_file method."""

    def test_analyzes_simple_function(self):
        """Test analyzes a simple function exceeding threshold."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            code = dedent(
                """
                def large_function():
                    # Line 1
                    # Line 2
                    # Line 3
                    # Line 4
                    # Line 5
                    # Line 6
                    # Line 7
                    # Line 8
                    # Line 9
                    # Line 10
                    # Line 11
                    # Line 12
                    # Line 13
                    # Line 14
                    # Line 15
                    # Line 16
                    # Line 17
                    # Line 18
                    # Line 19
                    # Line 20
                    # Line 21
                    # Line 22
                    # Line 23
                    # Line 24
                    # Line 25
                    # Line 26
                    # Line 27
                    # Line 28
                    # Line 29
                    # Line 30
                    # Line 31
                    pass
                """
            ).strip()
            f.write(code)
            f.flush()

            analyzer = FunctionAnalyzer(limit=30)
            result = analyzer.analyze_file(Path(f.name))

            assert len(result) == 1
            assert result[0].name == "large_function"
            assert result[0].code_lines > 30

    def test_excludes_small_functions(self):
        """Test does not report functions within threshold."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            code = dedent(
                """
                def small_function():
                    x = 1
                    y = 2
                    return x + y
                """
            ).strip()
            f.write(code)
            f.flush()

            analyzer = FunctionAnalyzer(limit=30)
            result = analyzer.analyze_file(Path(f.name))

            assert len(result) == 0

    def test_analyzes_function_with_docstring(self):
        """Test excludes docstring from code line count."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            code = dedent(
                '''
                def function_with_docstring():
                    """
                    This is a docstring.
                    It spans multiple lines.
                    """
                    # Line 1
                    # Line 2
                    # Line 3
                    # Line 4
                    # Line 5
                    # Line 6
                    # Line 7
                    # Line 8
                    # Line 9
                    # Line 10
                    # Line 11
                    # Line 12
                    # Line 13
                    # Line 14
                    # Line 15
                    # Line 16
                    # Line 17
                    # Line 18
                    # Line 19
                    # Line 20
                    # Line 21
                    # Line 22
                    # Line 23
                    # Line 24
                    # Line 25
                    # Line 26
                    # Line 27
                    # Line 28
                    # Line 29
                    # Line 30
                    # Line 31
                    pass
                '''
            ).strip()
            f.write(code)
            f.flush()

            analyzer = FunctionAnalyzer(limit=30)
            result = analyzer.analyze_file(Path(f.name))

            # Should find violation (31+ lines after docstring)
            assert len(result) == 1
            assert result[0].name == "function_with_docstring"

    def test_analyzes_class_methods(self):
        """Test analyzes methods inside classes."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            code = dedent(
                """
                class MyClass:
                    def large_method(self):
                        # Line 1
                        # Line 2
                        # Line 3
                        # Line 4
                        # Line 5
                        # Line 6
                        # Line 7
                        # Line 8
                        # Line 9
                        # Line 10
                        # Line 11
                        # Line 12
                        # Line 13
                        # Line 14
                        # Line 15
                        # Line 16
                        # Line 17
                        # Line 18
                        # Line 19
                        # Line 20
                        # Line 21
                        # Line 22
                        # Line 23
                        # Line 24
                        # Line 25
                        # Line 26
                        # Line 27
                        # Line 28
                        # Line 29
                        # Line 30
                        # Line 31
                        pass
                """
            ).strip()
            f.write(code)
            f.flush()

            analyzer = FunctionAnalyzer(limit=30)
            result = analyzer.analyze_file(Path(f.name))

            assert len(result) == 1
            assert result[0].name == "large_method"
            assert result[0].is_method is True
            assert result[0].class_name == "MyClass"

    def test_handles_syntax_errors_gracefully(self):
        """Test returns empty list for files with syntax errors."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def broken syntax here!")
            f.flush()

            analyzer = FunctionAnalyzer()
            result = analyzer.analyze_file(Path(f.name))

            assert result == []

    def test_handles_nonexistent_file(self):
        """Test returns empty list for nonexistent files."""
        analyzer = FunctionAnalyzer()
        result = analyzer.analyze_file(Path("/nonexistent/file.py"))

        assert result == []

    def test_avoids_duplicate_functions(self):
        """Test does not report same function twice."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            code = dedent(
                """
                def large_function():
                    # Line 1
                    # Line 2
                    # Line 3
                    # Line 4
                    # Line 5
                    # Line 6
                    # Line 7
                    # Line 8
                    # Line 9
                    # Line 10
                    # Line 11
                    # Line 12
                    # Line 13
                    # Line 14
                    # Line 15
                    # Line 16
                    # Line 17
                    # Line 18
                    # Line 19
                    # Line 20
                    # Line 21
                    # Line 22
                    # Line 23
                    # Line 24
                    # Line 25
                    # Line 26
                    # Line 27
                    # Line 28
                    # Line 29
                    # Line 30
                    # Line 31
                    pass
                """
            ).strip()
            f.write(code)
            f.flush()

            analyzer = FunctionAnalyzer(limit=30)
            result = analyzer.analyze_file(Path(f.name))

            # Should only find one violation, not duplicates
            assert len(result) == 1


# =============================================================================
# Test FunctionReporter
# =============================================================================


@pytest.mark.unit
class TestFunctionReporterInit:
    """Test FunctionReporter initialization."""

    def test_initialization(self):
        """Test reporter initializes with functions and threshold."""
        functions = [
            FunctionInfo(
                name="func1",
                file_path=Path("/test.py"),
                line_number=10,
                end_line=50,
                total_lines=41,
                code_lines=35,
                is_method=False,
                class_name=None,
            )
        ]
        reporter = FunctionReporter(functions, limit=30)

        assert reporter.functions == functions
        assert reporter.limit == 30


@pytest.mark.unit
class TestFunctionReporterSimpleList:
    """Test FunctionReporter.format_simple_list method."""

    def test_empty_list(self):
        """Test formats message when no violations found."""
        reporter = FunctionReporter([], limit=30)
        result = reporter.format_simple_list()

        assert result == "No violations found."

    def test_single_violation(self):
        """Test formats single violation."""
        functions = [
            FunctionInfo(
                name="large_func",
                file_path=Path("/test.py"),
                line_number=10,
                end_line=50,
                total_lines=41,
                code_lines=35,
                is_method=False,
                class_name=None,
            )
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_simple_list()

        assert "/test.py:10" in result
        assert "large_func()" in result
        assert "35 lines" in result

    def test_multiple_violations_sorted(self):
        """Test formats multiple violations sorted by size."""
        functions = [
            FunctionInfo("func1", Path("/a.py"), 10, 40, 31, 25, False, None),
            FunctionInfo("func2", Path("/b.py"), 20, 70, 51, 45, False, None),
            FunctionInfo("func3", Path("/c.py"), 30, 65, 36, 35, False, None),
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_simple_list()

        lines = result.split("\n")
        # Should be sorted by size descending (45, 35, 25)
        assert "45 lines" in lines[0]
        assert "35 lines" in lines[1]
        assert "25 lines" in lines[2]


@pytest.mark.unit
class TestFunctionReporterSummaryStats:
    """Test FunctionReporter.format_summary_stats method."""

    def test_no_violations(self):
        """Test summary when no violations found."""
        reporter = FunctionReporter([], limit=30)
        result = reporter.format_summary_stats()

        assert "No violations found" in result
        assert "limit: 30 lines" in result

    def test_summary_with_violations(self):
        """Test summary includes statistics."""
        functions = [
            FunctionInfo("func1", Path("/a.py"), 10, 50, 41, 40, False, None),
            FunctionInfo("func2", Path("/b.py"), 20, 80, 61, 60, False, None),
            FunctionInfo("func3", Path("/c.py"), 30, 60, 31, 50, False, None),
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_summary_stats()

        assert "Violations found: 3" in result
        assert "Average size:" in result
        assert "Largest function: 60 lines" in result
        assert "Top" in result


@pytest.mark.unit
class TestFunctionReporterDetailedReport:
    """Test FunctionReporter.format_detailed_report method."""

    def test_no_violations(self):
        """Test detailed report when no violations."""
        reporter = FunctionReporter([], limit=30)
        result = reporter.format_detailed_report()

        assert "No violations found" in result
        assert "limit: 30 lines" in result

    def test_categorizes_by_severity(self):
        """Test categorizes violations as critical/high/moderate."""
        functions = [
            FunctionInfo("critical1", Path("/a.py"), 10, 100, 91, 85, False, None),
            FunctionInfo("high1", Path("/b.py"), 20, 80, 61, 60, False, None),
            FunctionInfo("moderate1", Path("/c.py"), 30, 60, 31, 40, False, None),
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_detailed_report()

        assert "CRITICAL (>80 lines):" in result
        assert "HIGH PRIORITY (50-80 lines):" in result
        assert "MODERATE (30-50 lines):" in result
        assert "SUMMARY:" in result

    def test_includes_recommendations(self):
        """Test includes refactoring recommendations."""
        functions = [
            FunctionInfo("critical1", Path("/a.py"), 10, 100, 91, 85, False, None),
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_detailed_report()

        assert "Recommendation:" in result
        assert "Break into focused helper functions" in result


@pytest.mark.unit
class TestFunctionReporterJson:
    """Test FunctionReporter.format_json method."""

    def test_empty_json(self):
        """Test JSON format with no violations."""
        reporter = FunctionReporter([], limit=30)
        result = reporter.format_json()

        data = json.loads(result)
        assert data == []

    def test_json_with_violations(self):
        """Test JSON includes all function details."""
        functions = [
            FunctionInfo(
                name="func1",
                file_path=Path("/test.py"),
                line_number=10,
                end_line=50,
                total_lines=41,
                code_lines=35,
                is_method=False,
                class_name=None,
            )
        ]
        reporter = FunctionReporter(functions, limit=30)
        result = reporter.format_json()

        data = json.loads(result)
        assert len(data) == 1
        assert data[0]["name"] == "func1"
        assert data[0]["file"] == "/test.py"
        assert data[0]["line"] == 10
        assert data[0]["lines"] == 35
        assert data[0]["total_lines"] == 41
        assert data[0]["is_method"] is False
        assert data[0]["class_name"] is None
        assert data[0]["limit"] == 30


# =============================================================================
# Test CheckFunctionsTool Initialization
# =============================================================================


@pytest.mark.unit
class TestCheckFunctionsToolInit:
    """Test CheckFunctionsTool initialization."""

    def test_basic_initialization(self):
        """Test tool initializes with correct name and aliases."""
        tool = CheckFunctionsTool()

        assert tool.name == "check-funcs"
        assert "cf" in tool.config.aliases
        assert "code quality" in tool.config.help_text.lower()

    def test_initialization_with_parent(self):
        """Test tool initializes with parent."""
        parent = Mock()
        parent.lg = Mock()

        tool = CheckFunctionsTool(parent=parent)

        assert tool.name == "check-funcs"


# =============================================================================
# Test CheckFunctionsTool.add_args
# =============================================================================


@pytest.mark.unit
class TestCheckFunctionsToolAddArgs:
    """Test CheckFunctionsTool.add_args method."""

    def test_adds_dir_argument(self):
        """Test adds dir argument with default."""
        tool = CheckFunctionsTool()
        parser = Mock()

        tool.add_args(parser)

        calls = [c for c in parser.add_argument.call_args_list]
        dir_calls = [c for c in calls if c[0][0] == "dir"]
        assert len(dir_calls) == 1
        assert dir_calls[0][1].get("default") == "."

    def test_adds_threshold_argument(self):
        """Test adds --limit argument."""
        tool = CheckFunctionsTool()
        parser = Mock()

        tool.add_args(parser)

        calls = [c[0][0] for c in parser.add_argument.call_args_list]
        assert "--limit" in calls

    def test_adds_format_argument(self):
        """Test adds --format argument with choices."""
        tool = CheckFunctionsTool()
        parser = Mock()

        tool.add_args(parser)

        calls = [c for c in parser.add_argument.call_args_list]
        format_calls = [c for c in calls if c[0][0] == "--format"]
        assert len(format_calls) == 1

    def test_adds_strict_flag(self):
        """Test adds --strict flag for CI integration."""
        tool = CheckFunctionsTool()
        parser = Mock()

        tool.add_args(parser)

        calls = [c[0][0] for c in parser.add_argument.call_args_list]
        assert "--strict" in calls

    def test_adds_include_tests_flag(self):
        """Test adds --include-tests flag."""
        tool = CheckFunctionsTool()
        parser = Mock()

        tool.add_args(parser)

        calls = [c[0][0] for c in parser.add_argument.call_args_list]
        assert "--include-tests" in calls


# =============================================================================
# Test CheckFunctionsTool._should_exclude
# =============================================================================


@pytest.mark.unit
class TestShouldExclude:
    """Test CheckFunctionsTool._should_exclude method."""

    def test_excludes_test_directory(self):
        """Test excludes files in /tests/ directory by default."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        result = tool._should_exclude(Path("/project/tests/test_foo.py"), [], False)

        assert result is True

    def test_excludes_test_prefix(self):
        """Test excludes files starting with test_."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        result = tool._should_exclude(Path("/project/test_foo.py"), [], False)

        assert result is True

    def test_includes_test_files_when_flag_set(self):
        """Test includes test files when include_tests=True."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        result = tool._should_exclude(Path("/project/tests/test_foo.py"), [], True)

        assert result is False

    def test_excludes_custom_patterns(self):
        """Test excludes files matching custom patterns."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        result = tool._should_exclude(
            Path("/project/vendor/lib.py"), ["vendor/*"], False
        )

        assert result is True

    def test_includes_regular_files(self):
        """Test includes regular Python files."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        result = tool._should_exclude(Path("/project/infra/app.py"), [], False)

        assert result is False


# =============================================================================
# Test CheckFunctionsTool._collect_python_files
# =============================================================================


@pytest.mark.unit
class TestCollectPythonFiles:
    """Test CheckFunctionsTool._collect_python_files method."""

    def test_collects_files_in_directory(self):
        """Test collects all .py files in directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some Python files
            (Path(tmpdir) / "file1.py").touch()
            (Path(tmpdir) / "file2.py").touch()
            (Path(tmpdir) / "readme.txt").touch()

            tool = CheckFunctionsTool()
            tool._logger = Mock()

            files = tool._collect_python_files([tmpdir], [], False)

            assert len(files) == 2
            assert all(f.suffix == ".py" for f in files)

    def test_excludes_test_files_by_default(self):
        """Test excludes test files by default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "app.py").touch()
            (Path(tmpdir) / "test_app.py").touch()

            tool = CheckFunctionsTool()
            tool._logger = Mock()

            files = tool._collect_python_files([tmpdir], [], False)

            assert len(files) == 1
            assert files[0].name == "app.py"

    def test_includes_test_files_when_flag_set(self):
        """Test includes test files when include_tests=True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "app.py").touch()
            (Path(tmpdir) / "test_app.py").touch()

            tool = CheckFunctionsTool()
            tool._logger = Mock()

            files = tool._collect_python_files([tmpdir], [], True)

            assert len(files) == 2

    def test_handles_nonexistent_path(self):
        """Test logs warning for nonexistent paths."""
        tool = CheckFunctionsTool()
        tool._logger = Mock()

        files = tool._collect_python_files(["/nonexistent/path"], [], False)

        assert len(files) == 0
        tool._logger.warning.assert_called()

    def test_collects_single_file(self):
        """Test can collect a single .py file."""
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            tool = CheckFunctionsTool()
            tool._logger = Mock()

            files = tool._collect_python_files([f.name], [], False)

            assert len(files) == 1
            assert files[0].name == Path(f.name).name


# =============================================================================
# Test CheckFunctionsTool.run
# =============================================================================


@pytest.mark.unit
class TestCheckFunctionsToolRun:
    """Test CheckFunctionsTool.run method."""

    def test_returns_zero_when_no_violations(self):
        """Test returns 0 when no violations found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small function file
            test_file = Path(tmpdir) / "small.py"
            test_file.write_text("def small():\n    return 1\n")

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "simple"
            args.strict = False
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            assert result == 0

    def test_returns_warning_code_for_moderate_violations_non_strict(self):
        """Test returns EXIT_CODE_WARNING (42) for moderate-only violations in non-strict mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a moderate violation (40 lines = 30-50 range)
            test_file = Path(tmpdir) / "moderate.py"
            lines = ["def moderate():\n"] + [f"    x{i} = {i}\n" for i in range(40)]
            test_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "simple"
            args.strict = False
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            # Moderate violations only → warning (exit 42)
            assert result == EXIT_CODE_WARNING

    def test_returns_one_for_high_priority_violations_non_strict(self):
        """Test returns 1 for high priority violations (50-80 lines) even in non-strict mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a high priority violation (60 lines = 50-80 range)
            test_file = Path(tmpdir) / "high.py"
            lines = ["def high_priority():\n"] + [
                f"    x{i} = {i}\n" for i in range(60)
            ]
            test_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "simple"
            args.strict = False
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            # High priority violations fail even in non-strict mode
            assert result == 1

    def test_returns_one_for_critical_violations_non_strict(self):
        """Test returns 1 for critical violations (>80 lines) even in non-strict mode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a critical violation (90 lines = >80)
            test_file = Path(tmpdir) / "critical.py"
            lines = ["def critical():\n"] + [f"    x{i} = {i}\n" for i in range(90)]
            test_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "simple"
            args.strict = False
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            # Critical violations fail even in non-strict mode
            assert result == 1

    def test_returns_one_in_strict_mode_with_violations(self):
        """Test returns 1 in strict mode when violations found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large function file
            test_file = Path(tmpdir) / "large.py"
            lines = ["def large():\n"] + [f"    x{i} = {i}\n" for i in range(40)]
            lines.append("    return x0\n")
            test_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "simple"
            args.strict = True
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            assert result == 1

    def test_uses_custom_threshold(self):
        """Test respects custom threshold setting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a medium-sized function
            test_file = Path(tmpdir) / "medium.py"
            lines = ["def medium():\n"] + [f"    x{i} = {i}\n" for i in range(25)]
            lines.append("    return x0\n")
            test_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 20  # Lower threshold
            args.format = "simple"
            args.strict = True
            args.exclude = None
            args.include_tests = False
            tool._parsed_args = args

            result = tool.run()

            # Should find violation with threshold=20
            assert result == 1


# =============================================================================
# Integration Tests
# =============================================================================


@pytest.mark.integration
class TestCheckFunctionsToolIntegration:
    """Integration tests for CheckFunctionsTool."""

    def test_full_analysis_workflow(self):
        """Test complete analysis workflow with mixed functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            small_file = Path(tmpdir) / "small.py"
            small_file.write_text(
                dedent(
                    """
                def small_func():
                    return 1

                def another_small():
                    x = 1
                    y = 2
                    return x + y
            """
                ).strip()
            )

            large_file = Path(tmpdir) / "large.py"
            lines = ["def large_func():\n"] + [f"    x{i} = {i}\n" for i in range(40)]
            large_file.write_text("".join(lines))

            tool = CheckFunctionsTool()
            tool._logger = Mock()
            args = Mock()
            args.dir = tmpdir
            args.limit = 30
            args.format = "json"
            args.strict = False
            args.exclude = None
            args.include_tests = False
            args.quiet = False
            tool._parsed_args = args

            # Capture stdout
            import sys
            from io import StringIO

            captured = StringIO()
            old_stdout = sys.stdout
            sys.stdout = captured

            result = tool.run()

            sys.stdout = old_stdout
            output = captured.getvalue()

            # Should find one violation - non-strict mode returns warning code
            assert result == EXIT_CODE_WARNING
            data = json.loads(output)
            assert len(data) == 1
            assert data[0]["name"] == "large_func"
            assert data[0]["lines"] > 30

    def test_all_output_formats(self):
        """Test all output formats produce valid output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a large function
            test_file = Path(tmpdir) / "test.py"
            lines = ["def large():\n"] + [f"    x{i} = {i}\n" for i in range(40)]
            lines.append("    return x0\n")
            test_file.write_text("".join(lines))

            for fmt in ["simple", "summary", "detailed", "json"]:
                tool = CheckFunctionsTool()
                tool._logger = Mock()
                args = Mock()
                args.dir = tmpdir
                args.limit = 30
                args.format = fmt
                args.strict = False
                args.exclude = None
                args.include_tests = False
                args.quiet = False
                tool._parsed_args = args

                import sys
                from io import StringIO

                captured = StringIO()
                old_stdout = sys.stdout
                sys.stdout = captured

                result = tool.run()

                sys.stdout = old_stdout
                output = captured.getvalue()

                # Should produce some output
                assert len(output) > 0
                if fmt == "json":
                    # Validate JSON
                    data = json.loads(output)
                    assert len(data) > 0
