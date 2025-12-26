---
description: Analyze the infrastructure framework, provide comprehensive grading, and suggest
improvements
---

# ⚠️ CRITICAL: OUTPUT REQUIREMENTS

**WRITE THE COMPLETE GRADING REPORT TO `.GRADING.md` FILE**

- Use the Write tool to create/overwrite `.GRADING.md` with your full analysis
- The file should contain ALL sections below in markdown format
- This is NOT optional - the report MUST be written to the file
- After writing the file, provide a brief summary to the user

---

Analyze this Python infrastructure framework comprehensively and provide:

## 🔍 DETERMINE PROJECT TYPE

**CRITICAL: Read README.md to identify project type before grading:**

```bash
# Read README.md to detect project type from Scope & Philosophy section
head -50 README.md
```

**Look for explicit scope information:**
- Check for "Scope & Philosophy" or "Scope" section in README
- Look for keywords: "library", "framework", "reusable components" → LIBRARY
- Look for keywords: "application", "service", "deployed" → APPLICATION
- Check "In Scope" / "Out of Scope" / "Best For" / "Not For" declarations

**If README contains "Scope & Philosophy" section:**
- Use the explicit scope information to determine type
- Note any specific constraints (e.g., "PostgreSQL-only", "CLI framework not web framework")
- Identify what's explicitly out of scope

**If no explicit scope section exists:**
- Fall back to indicators:
  - PyPI publishing mentioned → likely library
  - Deployment guides for the project itself → likely application
  - "Install via pip" → library
  - "Run this service" → application

**Why This Matters:**
**Production readiness criteria differ significantly:**

| Criteria | Library | Application |
|----------|---------|-------------|
| Health checks | ❌ Not applicable (library doesn't run) | ✅ Required (/health endpoint) |
| Deployment guide | ❌ Not applicable (users deploy THEIR apps) | ✅ Required (how to deploy THIS app) |
| Metrics/observability | ✅ Hooks/abstractions for users to integrate | ✅ Built-in metrics endpoints |
| PyPI publishing | ✅ Critical for distribution | ❌ Not applicable |
| Integration examples | ✅ Show how to use in production apps | ⚠️ Less critical |
| API stability | ✅ Critical (semver, deprecation policy) | ⚠️ Less critical (internal APIs) |
| Production usage guide | ✅ How to use library in production settings | ✅ How to run application in production |

---

## 0. VERIFICATION STEPS - Run These First

**FIRST: Delete any existing grading report to avoid bias:**
```bash
# Remove old .GRADING.md file if it exists
rm -f .GRADING.md
```
- This prevents reading old analysis and being influenced by previous grading
- Critical: Do this BEFORE any analysis begins

**Before starting analysis, verify these critical facts:**

### LICENSE File
```bash
# Check LICENSE file exists and read first 20 lines
ls -la LICENSE
head -20 LICENSE
```
- Verify it contains actual license text (Apache, MIT, BSD, etc.)
- If file is empty or binary, that's a critical issue
- If file doesn't exist, that's a blocker

### CHANGELOG File
```bash
# Check CHANGELOG.md exists and read first 30 lines
ls -la CHANGELOG.md
head -30 CHANGELOG.md
```
- **IMPORTANT:** Actually READ this file before claiming it's missing
- Verify the file exists before making claims about its absence
- Check it contains actual changelog entries (versions, dates, changes)
- Common formats: Keep a Changelog, conventional commits
- If file doesn't exist, note it as a documentation gap (not a blocker)

### Test Files Location
```bash
# Check for tests in standard locations
find . -type d -name "tests" -o -name "test"
find ./tests -name "*.py" 2>/dev/null | wc -l
find . -name "test_*.py" -o -name "*_test.py" | head -20
```
- Tests may be in: `./tests/`, `./test/`, `infra/tests/`, or mixed with source
- Count test files accurately before making claims
- If README claims X tests but you find Y, investigate why

### Test Execution & Coverage - CRITICAL: RUN THE TESTS

**IMPORTANT: Actually run the test suite to get real metrics:**

```bash
# 1. Run all tests (unit, integration, performance, security, e2e)
make test.all

# 2. Generate coverage report
make test.coverage

# 3. Display coverage summary
~/.venv/bin/python -m coverage report

# 4. Verify test collection count
~/.venv/bin/python -m pytest --collect-only 2>&1 | grep "collected"
```

**What to capture:**
- Total tests run (passed/failed/skipped)
- Test execution time
- Actual coverage percentage (not README claims)
- Coverage by module (which modules have gaps)
- Any test failures or errors

**If tests fail:**
- Document which tests failed and why
- This is CRITICAL information for the grading
- Don't just report "tests passed" - show actual results
- Test failures may reveal bugs, missing dependencies, or config issues

**Cross-check with your file count:**
- If you found 70 test files but pytest collected 2,308 tests → explain (multiple tests per file)
- If coverage report shows 85% but README claims 93% → report discrepancy

### Type Hints Coverage - CRITICAL: RUN THE SCRIPT

**IMPORTANT: Use the automated script to get real type hint coverage:**

```bash
# Run type hint coverage report
./scripts/type-hint.sh
```

**This script will:**
- Run mypy on all production code (appinfra/, cli/)
- Count files successfully checked by mypy
- Count total production Python files
- Calculate and display coverage percentage
- Show mypy configuration from pyproject.toml

**What to capture:**
- "Files with complete type hints: X"
- "Total production files: Y"
- "Coverage: Z%"
- Mypy config showing `disallow_untyped_defs = true`

**Key insight:**
If mypy passes with `disallow_untyped_defs = true` enabled, this **PROVES** that all checked files
have complete type hints. Any file without type hints would FAIL mypy with this strict setting.

**Use these exact numbers in the grading report** - never estimate or guess type hint coverage.

---

## ⚠️ IMPORTANT VERIFICATION REQUIREMENT

Before grading type hint coverage:
1. ✅ Run `./scripts/type-hint.sh` to get actual coverage
2. ✅ Use exact numbers from script output
3. ✅ Verify script shows mypy config has `disallow_untyped_defs = true`
4. ❌ NEVER estimate or guess type hint coverage

---

## 1. COMPREHENSIVE GRADING

Grade each category on a 10-point scale with detailed justification:

### Architecture & Design
- Design patterns used (Builder, Factory, Protocol, etc.)
- Module organization and cohesion
- Abstraction quality
- Technical debt (deprecated APIs, global state)
- API consistency

### Code Quality
- Type hints coverage
- Function sizes (should be 20-30 lines per guidelines) - **Run `./cli/cli.py cq cf --format=detailed` to check**
- Documentation completeness
- Naming consistency
- Production-ready error handling (no print() statements in executable code)
  - **IMPORTANT: Verifying print() statements** - Many print() occurrences may be in docstrings, comments, or documentation
  - **Pattern to check**: Use `grep -rn "print(" --include="*.py" path/` to get all occurrences
  - **Then verify which are executable vs. documentation**:
    - **Executable**: Inside function bodies, not in docstrings/comments
    - **Documentation**: In module/function/class docstrings, README files, comment blocks, example code
  - **Check the context** of each occurrence before counting
  - **Example**: `ticker.py` may show 12 print() but only 4 are executable (rest in docstrings)
  - **Don't count**: Docstring examples, README files, comment blocks, example scripts in `examples/`

### Security
- Input validation
- Resource limits
- Vulnerability assessment (YAML parsing, path traversal, ReDoS)
- Credential handling
- Example security

### Testing
- **CRITICAL: Run the tests first** - Execute `make test.all` and `make test.coverage` before grading
- **Use actual results, not claims:**
  - Report actual coverage % from `coverage report` (not README)
  - Report actual test count from pytest output
  - Document any test failures or errors
  - Show execution time for different test categories
- Test coverage by category (unit, integration, performance, security, e2e)
- Test organization and structure
- Edge case coverage in critical paths
- Performance test assertions (actual benchmarks with thresholds, not just execution)
- Test isolation and independence
- **Cross-check**: If `pytest --collect-only` shows N tests but you found M files, explain discrepancy
- **Coverage gaps**: Identify modules with < 80% coverage from coverage report

### Documentation
- README quality (completeness, examples, structure)
- API documentation (docstrings, generated docs)
- Migration guides for deprecated APIs
- Security documentation (SECURITY.md quality)
- **LICENSE file**: READ the file (not just check presence) - verify it contains valid license text
  - Common licenses: Apache 2.0, MIT, BSD, GPL
  - If file exists but is empty/binary/corrupted, that's CRITICAL
  - Check copyright year and attribution

### Production Readiness

**Grade based on project type (see "DETERMINE PROJECT TYPE FIRST" section above):**

#### For Libraries:
- ✅ **API Stability:** Clear versioning (semver), deprecation warnings, backward compatibility policy
- ✅ **Package Distribution:** Published to PyPI, installable via pip, proper wheel distribution
- ✅ **Integration Guidance:** How to use library in production apps, configuration examples, best practices
- ✅ **Production Patterns:** Examples of production-grade usage (structured logging, connection pooling, etc.)
- ✅ **Error Handling:** Graceful errors, custom exceptions, resource cleanup (context managers)
- ✅ **Observability Hooks:** Callbacks/hooks for users to integrate metrics (not built-in dashboards)
- ❌ **NOT Expected:** Health check endpoints, deployment guides for the library itself, metrics dashboards

#### For Applications:
- ✅ **Graceful Shutdown:** Signal handlers, cleanup hooks, proper resource release
- ✅ **Health Checks:** /health endpoint, dependency checks
- ✅ **Metrics/Observability:** Built-in metrics endpoints (Prometheus, StatsD, etc.)
- ✅ **Deployment Guide:** How to deploy THIS application (Docker, K8s, systemd, etc.)
- ✅ **Error Recovery:** Retry logic, circuit breakers, fallback strategies
- ✅ **Version Management:** Runtime version checks, feature flags

#### Universal (Both Types):
- Error handling and recovery strategies
- Resource management (cleanup, context managers)
- Version management and compatibility

### Dependencies & Compatibility
- Python version support (check if supporting EOL versions)
- Dependency pinning
- CI/CD matrix testing
- Platform compatibility

## 2. CRITICAL ISSUES

Identify and prioritize:
- **Tier 0: Must-Fix** (before any release) - Legal blockers, breaking bugs
- **Tier 1: High-Impact** (before open-source) - Security, observability, docs
- **Tier 2: Quality** (before 1.0) - Technical debt, refactoring
- **Tier 3: Polish** (ongoing) - Nice-to-haves, future enhancements

For each issue provide:
- File location with line numbers
- Code example showing the problem
- Impact assessment
- Specific fix recommendation with code example
- Time estimate

**Note on Project Type:** Remember to frame issues based on whether this is a library or
application. For example:
- Library missing PyPI publishing → Tier 1 (high-impact)
- Library missing health check endpoint → Not an issue (libraries don't need this)
- Application missing deployment guide → Tier 1 (high-impact)
- Application missing PyPI publishing → Not applicable

## 3. KEY METRICS

Measure and report (use ACTUAL data from running commands):
- Total lines of code
- Number of implementation files
- Number of test files (from `find` command)
- Number of test functions (from `pytest --collect-only`)
- Test-to-code ratio
- **Actual test coverage** - from `coverage report` output, NOT README claims
  - Overall coverage percentage
  - Coverage by module (identify gaps)
  - Lines covered vs total lines
- **Test execution results:**
  - Total tests run
  - Passed / Failed / Skipped counts
  - Execution time by category
- Function size statistics (average, max) - **Use `./cli/cli.py cq cf --format=detailed` for this**
- Deprecated API usage

## 4. TRADE-OFFS & RECOMMENDATIONS

Analyze key decisions with options:
- Python version support strategy
- API design choices (multiple ways to do things)
- Observability approach
- Documentation strategy

For each, provide:
- Current state
- Options (A, B, C with pros/cons)
- Recommended approach with rationale
- Migration path if applicable

## 5. ACTIONABLE ROADMAP

Create phased plan:
- **Phase 1: Release Blockers** (days) - Time estimate, must-fix list
- **Phase 2: Quality & Hardening** (weeks) - High-priority improvements
- **Phase 3: Polish & Enhancement** (weeks) - Medium-priority

## 6. FINAL SCORECARD

### 🚨 MANDATORY: Deduction Evidence Requirement

**YOU CANNOT MAKE A DEDUCTION WITHOUT INLINE PROOF.**

Every deduction MUST include verification evidence in this exact format:

```markdown
**Deduction (-0.5): [Claim]**

Verification:
```bash
[Command you actually ran]
```
Result:
> [Actual output that proves the issue exists]

Therefore: [Brief explanation of why this justifies deduction]
```

**Examples of VALID deductions:**

```markdown
**Deduction (-0.5): SECURITY.md missing**

Verification:
```bash
ls -la SECURITY.md
```
Result:
> ls: cannot access 'SECURITY.md': No such file or directory

Therefore: Security documentation is missing, which is required for production libraries.
```

**Examples of INVALID deductions (will be rejected):**

```markdown
❌ **Deduction (-0.5): Documentation seems sparse**
   → No verification command shown

❌ **Deduction (-0.5): Error handling could be better**
   → No specific file:line reference, no evidence

❌ **Deduction (-0.5): No CI/CD configuration**
   → Must run `ls .github/workflows/` first to prove it
```

**The Rule:**
- If you cannot show a command you ran AND its output, you cannot make the deduction
- "I looked at the code" is not verification - show the grep/read command
- Pattern-matching assumptions are not evidence - prove it with commands

---

### ⚠️ MANDATORY: Score Justification Format

**For EACH category, you MUST use this exact format:**

```markdown
### [Category Name]: X/10

**If score is 10/10:**
- No weaknesses identified that justify deduction

**If score is < 10/10, MUST list:**
- **Deduction 1 (-0.5):** [Specific issue with file:line reference]
  - Verification: `[command run]`
  - Result: [output proving issue]
- **Deduction 2 (-0.5):** [Specific issue with file:line reference]
  - Verification: `[command run]`
  - Result: [output proving issue]
- **Total deductions:** -X points → Score: Y/10
```

### 🛑 STOP: Pre-Write Consistency Check

**Before writing the scorecard to .GRADING.md, answer these questions for EACH category:**

| Category | Score | Weaknesses Listed? | If "None" → Should be 10? | Deductions Justified? |
|----------|-------|-------------------|---------------------------|----------------------|
| Architecture | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Code Quality | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Security | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Testing | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Documentation | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Production Ready | ?/10 | Yes/None | ✓/✗ | Yes/No |
| Dependencies | ?/10 | Yes/None | ✓/✗ | Yes/No |

**Rules:**
1. If "Weaknesses Listed?" = "None" and Score < 10 → **FIX IT** (raise to 10 or add real weakness)
2. If "Deductions Justified?" = "No" → **FIX IT** (verify weakness or remove deduction)
3. Every 0.5 point deduction needs a specific, verified issue

### Common Scoring Mistakes to Avoid

❌ **WRONG:** "Weaknesses: None significant" + Score: 9.5/10
✅ **RIGHT:** "Weaknesses: None significant" + Score: 10/10

❌ **WRONG:** Deducting for things out of scope (library missing health checks)
✅ **RIGHT:** Only deduct for issues IN SCOPE for the project type

❌ **WRONG:** Arbitrary "nothing is perfect" deductions
✅ **RIGHT:** Every deduction tied to a specific, verifiable issue

### Final Scorecard Format

Summary table with:
- Category grades (A-F scale)
- Numerical scores (0-10)
- Weighted average
- Overall grade

**Include the completed consistency check table in the report to prove you did it.**

## IMPORTANT INSTRUCTIONS

- **RUN THE TESTS** - Execute `make test.all` and `make test.coverage` BEFORE grading
- **Use actual data, not claims** - Don't trust README stats, verify with commands
- **Be analytically rigorous** - Point out actual weaknesses, not just praise
- **Be specific** - Include file paths, line numbers, code examples
- **Be actionable** - Every issue needs a concrete fix with time estimate
- **Use evidence** - Base assessments on actual code inspection and test results
- **Check for breaking issues** - Especially deprecated Python features (like `abc.abstractproperty`)
- **Verify security** - Look for YAML vulnerabilities, path traversal, print() in production
- **Measure metrics** - Count files, lines, calculate ratios from actual commands
- **Document test failures** - If any tests fail, this is CRITICAL for grading

Focus analysis on:
- `infra/app/` - Application framework
- `infra/log/` - Logging system
- `infra/db/` - Database layer
- `infra/net/` - Network components
- `infra/time/` - Time utilities
- Root configuration files (pyproject.toml, README.md, etc.)

## COMMON PITFALLS TO AVOID

0. **MOST CRITICAL: Verify before deducting**
   - ❌ "Documentation seems sparse" → Did you count the lines? Read the file?
   - ❌ "No CI/CD exists" → Did you run `ls .github/workflows/`?
   - ❌ "Error handling is weak" → Did you read the actual error handling code?
   - ❌ "Feature X is not documented" → Did you grep for it in docs/?
   - ✅ Every deduction requires a verification command AND its output
   - ✅ If you can't prove it with a command, you can't deduct for it

1. **MOST CRITICAL: Actually RUN the tests**
   - ❌ Don't just read test files and assume they pass
   - ❌ Don't trust README coverage claims without verification
   - ✅ Run `make test.all` to see actual test results
   - ✅ Run `make test.coverage` to get real coverage numbers
   - ✅ Document any test failures - this affects the grade significantly
   - If tests fail, investigate why (missing deps, config, bugs)

2. **LICENSE File**: Always READ it, don't just check file size
   - Use `head -20 LICENSE` to see actual content
   - Empty or binary LICENSE file is a critical blocker

3. **Test Files**: Search in multiple locations
   - Use `find . -name "test_*.py"` not `find infra/ -name "test_*.py"`
   - Check `./tests/`, `./test/`, and project subdirectories
   - Cross-reference with `pytest --collect-only` output

4. **Test Count Discrepancies**: If numbers don't match, investigate
   - pytest may find more tests (multiple tests per file)
   - Test files may be excluded by pytest.ini
   - Some files may be fixtures, not actual tests

5. **Don't Trust Assumptions**: Verify with actual commands
   - If README says "93% coverage" → RUN `coverage report` to verify
   - If you see 11KB LICENSE → read it to confirm it's valid
   - If `find` returns 0 results → try different search patterns
   - Test failures reveal real issues - don't ignore them

6. **Search Pattern Mistakes**:
   - ❌ `grep -rn "print(" infra/` - only searches infra/
   - ✅ `grep -rn "print(" .` - searches entire repo
   - ❌ `find infra/ -name "*.py"` - misses tests/
   - ✅ `find . -name "*.py"` - finds all Python files

7. **Negative Claims Require Proof** (claiming something is MISSING):
   - Before claiming "X doesn't exist" or "Y is missing", you MUST run a command to verify
   - Examples of claims that require verification:
     - "No CI/CD" → `ls .github/workflows/`
     - "No security docs" → `ls SECURITY.md` and `grep -r "security" docs/`
     - "Feature undocumented" → `grep -rn "feature_name" docs/`
     - "No error handling" → Read the actual code with `Read` tool
   - If your verification command finds the thing exists, DO NOT make the deduction
   - Pattern-matching ("this looks like it might be missing") is not evidence

8. **Complexity is not a defect when it's justified**:
   - Don't deduct for "complexity" if:
     - The complexity solves a real problem (e.g., subprocess isolation for GIL bypass)
     - Simpler alternatives are available (e.g., direct mode vs subprocess mode)
     - The complexity is well-documented
   - Ask: "Is this complexity necessary and justified?" not "Is this complex?"
