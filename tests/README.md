# ns-3 GUI Test Suite

This directory contains the test suite for validating the ns-3 GUI application's ability to build, compile, and run all components of the ns-3 simulator.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and helper functions
├── unit/                            # Fast, isolated unit tests
│   ├── test_models.py               # NetworkModel, NodeModel, LinkModel, etc.
│   ├── test_script_generator.py     # NS-3 script generation validation
│   └── test_serialization.py        # Save/load topology and flows
├── integration/                     # Component interaction tests
│   └── test_project_workflow.py     # Project create/open/save workflows
└── e2e/                             # End-to-end tests (require ns-3)
    └── test_ns3_execution.py        # Full simulation execution tests
```

## Requirements

```bash
pip install pytest pytest-cov
```

## Running Tests

### Using the Test Runner Script

```bash
# Run all tests (excludes slow tests by default)
python run_tests.py

# Run specific test suites
python run_tests.py unit          # Unit tests only
python run_tests.py integration   # Integration tests only
python run_tests.py e2e           # End-to-end tests (requires ns-3)

# Include slow tests
python run_tests.py --slow

# Generate coverage report
python run_tests.py --coverage

# Verbose output with stop on first failure
python run_tests.py -v --failfast
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/unit/test_models.py

# Run specific test class
pytest tests/unit/test_models.py::TestNodeModel

# Run specific test
pytest tests/unit/test_models.py::TestNodeModel::test_create_host

# Run with verbose output
pytest tests/ -v

# Stop on first failure
pytest tests/ -x

# Run tests matching a pattern
pytest tests/ -k "test_save"

# Skip slow tests
pytest tests/ -m "not slow"

# Generate coverage report
pytest tests/ --cov=. --cov-report=term-missing --cov-report=html
```

## Test Categories

| Category | Directory | Purpose | Speed | ns-3 Required |
|----------|-----------|---------|-------|---------------|
| Unit | `tests/unit/` | Test individual classes and functions in isolation | Fast (~seconds) | No |
| Integration | `tests/integration/` | Test component interactions and workflows | Medium (~seconds) | No |
| E2E | `tests/e2e/` | Test complete simulation pipeline | Slow (~minutes) | **Yes** |

## Test Markers

Tests can be marked with pytest markers:

- `@pytest.mark.slow` - Tests that take a long time to run
- `@pytest.mark.e2e` - End-to-end tests requiring ns-3
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests

## Unit Tests

### test_models.py
Tests for core model classes:
- `TestNodeModel` - Node creation, properties, routing tables
- `TestLinkModel` - Link creation and properties
- `TestNetworkModel` - Network operations (add/remove nodes/links)
- `TestPortConfig` - Port configuration
- `TestRouteEntry` - Routing table entries

### test_script_generator.py
Tests for ns-3 script generation:
- `TestScriptGeneration` - Basic script generation
- `TestTrafficFlowGeneration` - UDP Echo, OnOff, multiple flows
- `TestCustomApplicationGeneration` - Custom app imports
- `TestScriptValidation` - Error handling

### test_serialization.py
Tests for topology save/load:
- `TestTopologySerialization` - Save/load JSON files
- `TestFlowSerialization` - Traffic flow persistence
- `TestSchemaValidation` - Invalid file handling
- `TestComplexTopologies` - Star, routed networks

## Integration Tests

### test_project_workflow.py
Tests for project management:
- `TestProjectCreation` - Create new projects
- `TestProjectSaving` - Save topology, flows, scripts
- `TestProjectLoading` - Load project components
- `TestRunHistory` - Simulation run records
- `TestProjectWorkflow` - Complete workflow scenarios

## End-to-End Tests

### test_ns3_execution.py
Tests requiring a working ns-3 installation:
- `TestNS3Detection` - Detect ns-3 installation
- `TestScriptExecution` - Run generated scripts
- `TestErrorHandling` - Invalid scripts, timeouts
- `TestResultsParsing` - FlowMonitor XML parsing
- `TestScenarios` - Star topology, routed networks

**Note:** E2E tests are automatically skipped if ns-3 is not available.

## Fixtures

Common fixtures defined in `conftest.py`:

| Fixture | Description |
|---------|-------------|
| `temp_dir` | Temporary directory for test files |
| `temp_workspace` | Temporary workspace structure |
| `empty_network` | Empty NetworkModel |
| `simple_network` | 2-node network with one link |
| `star_network` | Switch with 4 hosts |
| `routed_network` | Router connecting two hosts |
| `basic_sim_config` | Basic SimulationConfig |
| `sim_config_with_flow` | Config with traffic flow |
| `project_manager` | ProjectManager with temp workspace |
| `test_project` | Created test project |
| `script_generator` | NS3ScriptGenerator instance |

## Helper Functions

```python
from tests.conftest import assert_valid_python, assert_contains_all

# Verify code is valid Python syntax
assert_valid_python(code, filename="test.py")

# Verify text contains all substrings
assert_contains_all(text, ["import", "NodeContainer", "Simulator"])
```

## Writing New Tests

1. **Choose the right category:**
   - Unit: Testing a single function/class
   - Integration: Testing multiple components together
   - E2E: Testing with real ns-3

2. **Use fixtures:**
   ```python
   def test_my_feature(simple_network, temp_dir):
       # Use provided fixtures
       pass
   ```

3. **Mark slow tests:**
   ```python
   @pytest.mark.slow
   def test_long_running():
       pass
   ```

4. **Handle ns-3 dependency:**
   ```python
   @pytest.mark.skipif(not ns3_available, reason="ns-3 not installed")
   def test_requires_ns3():
       pass
   ```

## Coverage Report

After running with `--coverage`, view the HTML report:

```bash
# Generate report
python run_tests.py --coverage

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```

## Continuous Integration

Example GitHub Actions workflow:

```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: python run_tests.py unit integration --coverage
```
