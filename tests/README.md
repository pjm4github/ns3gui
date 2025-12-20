# ns-3 GUI Test Suite

This directory contains the test suite for validating the ns-3 GUI application's ability to build, compile, and run all components of the ns-3 simulator.

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and pytest configuration
├── unit/                            # Fast, isolated unit tests
│   ├── test_models.py               # NetworkModel, NodeModel, LinkModel, etc.
│   ├── test_grid_models.py          # Grid node, link, and traffic models
│   ├── test_grid_generator.py       # Grid ns-3 script generation
│   ├── test_script_generator.py     # NS-3 script generation validation
│   └── test_serialization.py        # Save/load topology and flows
├── integration/                     # Component interaction tests
│   └── test_project_workflow.py     # Project create/open/save workflows
└── e2e/                             # End-to-end tests (require ns-3)
    ├── test_ns3_execution.py        # Basic ns-3 execution tests
    └── test_grid_simulation.py      # Grid SCADA network simulation tests
```

## Requirements

```bash
pip install pytest pytest-cov
```

## Running Tests

### Using the Test Runner Script

```bash
# Run unit + integration tests (default, excludes slow/e2e)
python run_tests.py

# Run specific test suites
python run_tests.py unit          # Unit tests only
python run_tests.py integration   # Integration tests only
python run_tests.py e2e           # E2E tests (auto-enables --slow, requires ns-3)
python run_tests.py all           # All tests (use with --slow for e2e)

# Include slow tests (required for e2e simulation tests)
python run_tests.py --slow
python run_tests.py all --slow    # Run everything including e2e

# Generate coverage report
python run_tests.py --coverage

# Verbose output with stop on first failure
python run_tests.py -v -x

# Check ns-3 configuration status
python run_tests.py --show-ns3
```

### Running E2E Grid Simulation Tests

E2E tests run actual ns-3 simulations. They require:
1. ns-3 installed (with Python bindings built)
2. On Windows: ns-3 must be installed inside WSL

```bash
# Check if ns-3 is detected
python run_tests.py --show-ns3

# Run all e2e tests (--slow is auto-enabled)
python run_tests.py e2e

# Run specific grid simulation test
python -m pytest tests/e2e/test_grid_simulation.py::TestGridSimulationE2E::test_scada_polling -v --run-slow

# Run all grid simulation tests
python -m pytest tests/e2e/test_grid_simulation.py -v --run-slow
```

**Configure ns-3 path** (if auto-detection fails):
- Via GUI: Run `python main.py` → Simulation → Configure ns-3 Path
- The path is saved to settings and used by e2e tests

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

# Run slow tests (required for e2e)
pytest tests/ --run-slow

# Skip slow tests (default behavior)
pytest tests/

# Generate coverage report
pytest tests/ --cov=models --cov=services --cov-report=term-missing
```

## Test Categories

| Category | Directory | Purpose | Speed | ns-3 Required |
|----------|-----------|---------|-------|---------------|
| Unit | `tests/unit/` | Test individual classes and functions in isolation | Fast (~seconds) | No |
| Integration | `tests/integration/` | Test component interactions and workflows | Medium (~seconds) | No |
| E2E | `tests/e2e/` | Test complete simulation pipeline with real ns-3 | Slow (~minutes) | **Yes** |

## Test Markers

Tests can be marked with pytest markers:

- `@pytest.mark.slow` - Tests that take a long time to run (skipped by default)
- `@pytest.mark.e2e` - End-to-end tests requiring ns-3
- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests

**Important:** Use `--run-slow` to run slow/e2e tests.

## Unit Tests

### test_models.py
Tests for core model classes:
- `TestNodeModel` - Node creation, properties, routing tables
- `TestLinkModel` - Link creation and properties
- `TestNetworkModel` - Network operations (add/remove nodes/links)
- `TestPortConfig` - Port configuration
- `TestRouteEntry` - Routing table entries

### test_grid_models.py
Tests for grid-specific models:
- `TestGridNodeModel` - Grid node types (RTU, IED, Control Center)
- `TestGridLinkModel` - Grid link types (Fiber, Satellite, Cellular)
- `TestGridTrafficFlow` - SCADA traffic classes
- `TestFailureScenario` - Failure injection models

### test_grid_generator.py
Tests for grid ns-3 script generation:
- `TestGridNS3GeneratorBasic` - Generator instantiation
- `TestGridLinkGeneration` - Fiber, satellite, cellular links
- `TestSCADAApplicationGeneration` - Polling, GOOSE, control traffic
- `TestFailureInjection` - Link/node failure scheduling
- `TestCompleteGridSimulation` - Full script generation

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
Basic tests requiring ns-3:
- `TestNS3Detection` - Detect ns-3 installation
- `TestScriptExecution` - Run generated scripts
- `TestErrorHandling` - Invalid scripts, timeouts
- `TestResultsParsing` - FlowMonitor XML parsing
- `TestScenarios` - Star topology, routed networks

### test_grid_simulation.py
Grid SCADA simulation tests (run actual ns-3):
- `TestGridSimulationE2E` - Full simulation tests:
  - `test_simple_two_node` - Basic CC + RTU network
  - `test_scada_polling` - Polling multiple RTUs
  - `test_satellite_link` - GEO satellite with 540ms RTT
  - `test_link_failure_injection` - Scheduled link failures
  - `test_mixed_link_types` - Fiber + Radio + Cellular
- `TestGridSimulationValidation` - Result validation:
  - `test_packet_delivery` - Verify packets are delivered
- `TestScriptGeneration` - Script structure validation

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
| `ns3_config` | ns-3 path and WSL setting (e2e only) |
| `grid_generator` | GridNS3Generator instance (e2e only) |

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
   @pytest.mark.e2e
   def test_long_running(ns3_config, grid_generator):
       ns3_path, use_wsl = ns3_config
       # Test with real ns-3
       pass
   ```

4. **Handle ns-3 dependency:**
   ```python
   @pytest.fixture
   def ns3_config():
       ns3_path, use_wsl = get_ns3_config()
       if ns3_path is None:
           pytest.skip("ns-3 not found")
       return ns3_path, use_wsl
   ```

## Coverage Report

After running with `--coverage`, view the HTML report:

```bash
# Generate report
python run_tests.py --coverage

# Open in browser
open coverage_report/index.html  # macOS
xdg-open coverage_report/index.html  # Linux
start coverage_report/index.html  # Windows
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
          python-version: '3.11'
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: python run_tests.py unit integration --coverage
```
