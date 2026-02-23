# Integration Tests for OrbStack NixOS Provisioning

This directory contains comprehensive integration tests for the OrbStack NixOS provisioning system.

## Prerequisites

1. **OrbStack** must be installed and running
2. **Python 3.8+** required
3. **pytest** and test dependencies

Install test dependencies:

```bash
# Using pip (from project root)
pip install -e ".[dev,test]"

# Or using Nix
nix develop
```

## Test Structure

```
tests/
├── __init__.py                      # Package marker
├── conftest.py                      # Pytest fixtures and configuration
├── utils.py                         # Test utility functions
├── fixtures/                        # Static test fixtures
│   └── README.md
├── test_machine_creation.py         # Machine creation tests
├── test_nix_flakes.py              # Nix flakes integration tests
├── test_extra_config.py            # --extra-config functionality tests
├── test_nix_extra_config_dir.py    # orbstack-nix-config/extra directory tests
├── test_architecture.py            # Architecture detection tests
└── test_e2e.py                     # End-to-end workflow tests
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run specific test file

```bash
pytest tests/test_machine_creation.py
```

### Run specific test

```bash
pytest tests/test_machine_creation.py::test_create_machine_default_settings
```

### Skip slow tests

```bash
pytest -m "not slow"
```

### Run only fast tests

```bash
pytest -m "not slow"
```

### Run tests in parallel

```bash
pytest -n auto
```

### Run with verbose output

```bash
pytest -v
```

### Run with test output capture disabled

```bash
pytest -s
```

## Test Categories

### Machine Creation Tests (`test_machine_creation.py`)

Tests basic machine creation, deletion, and management:
- Default settings
- Custom hostname/username
- Machine already exists error handling
- `--recreate` flag functionality
- Machine deletion

### Nix Flakes Tests (`test_nix_flakes.py`)

Tests Nix flakes integration:
- Flake files copied to `/etc/nixos/`
- Flake content matches source
- `nixos-rebuild` on existing machines
- Configuration changes applied
- Flake evaluation in impure mode

### Extra Config Tests (`test_extra_config.py`)

Tests `--extra-config` functionality:
- Simple package installation
- Marker file verification
- Extra config on rebuild
- Relative and absolute paths
- Integration with `orbstack-nix-config/extra/lib/` files
- Environment variable passing

### Nix Extra Config Directory Tests (`test_nix_extra_config_dir.py`)

Tests `orbstack-nix-config/extra/` directory copying:
- Directory recursively copied to VM
- Nested structure preservation
- File content verification
- Recopy on rebuild
- Multiple files handling
- Works without directory

### Architecture Tests (`test_architecture.py`)

Tests architecture detection and mapping:
- Auto-detection of host architecture
- Explicit ARM architecture flags (aarch64, arm64)
- Explicit x86 architecture flags (x86_64, amd64)
- Architecture mapping function
- Invalid architecture handling
- Flake attribute matching

### End-to-End Tests (`test_e2e.py`)

Complete workflow tests:
- Full create → verify → rebuild → delete workflow
- Multiple sequential rebuilds (idempotency)
- SSH connectivity
- Docker workflow
- Configuration persistence
- System packages verification
- Nix flakes enabled
- User permissions (wheel group, sudo)

## Test Markers

- **`@pytest.mark.slow`**: Tests that take longer to run (creates/provisions machines)
- **`@pytest.mark.requires_orbstack`**: Tests that require OrbStack to be installed

## Fixtures

### Session Fixtures

- `project_root`: Path to project root directory
- `test_username`: Current user's username
- `sample_configs_dir`: Directory with sample NixOS config files

### Function Fixtures

- `unique_machine_name`: Generates unique machine name for testing
- `test_machine`: Provides machine name and handles cleanup
- `test_machine_created`: Pre-creates a machine for testing

## Timeouts

Default timeout for tests: **300 seconds (5 minutes)**

Tests creating/provisioning machines may take longer and have explicit timeouts of **600 seconds (10 minutes)**.

## Safety Features

1. **Unique machine names**: Each test uses timestamped names to avoid conflicts
2. **Automatic cleanup**: Fixtures ensure machines are deleted even on test failure
3. **Skip if no OrbStack**: Tests are skipped if OrbStack is not installed
4. **Isolated configs**: Sample configs generated in temporary directories

## Debugging Failed Tests

### Check test output

```bash
pytest -v -s
```

### Run single failing test

```bash
pytest tests/test_file.py::test_name -v -s
```

### Check machine state

If a test fails, the machine may still exist:

```bash
orb list
```

### Manually clean up test machines

```bash
orb list | grep test-orbstack | awk '{print $1}' | xargs -I {} orb delete -f {}
```

### Increase timeout for slow environments

Edit `pytest.ini` and increase the `timeout` value.

## Writing New Tests

1. Import necessary utilities from `tests/utils.py`
2. Use appropriate fixtures (`test_machine`, `test_machine_created`)
3. Add `@pytest.mark.slow` for tests that create/provision machines
4. Add `@pytest.mark.requires_orbstack` for tests requiring OrbStack
5. Ensure cleanup in case of test failure (fixtures handle this automatically)
6. Use unique machine names from fixtures

Example:

```python
@pytest.mark.slow
@pytest.mark.requires_orbstack
def test_my_feature(test_machine, project_root, test_username):
    """Test my new feature."""
    machine_name = test_machine
    # ... test code ...
    # Cleanup is automatic via test_machine fixture
```

## CI/CD Integration

These tests can be integrated into CI/CD pipelines. Note that:

1. OrbStack must be installed on the CI runner
2. Tests may take 10-30 minutes to complete
3. Consider running only fast tests in CI: `pytest -m "not slow"`
4. Use parallel execution: `pytest -n auto`

## Troubleshooting

### "OrbStack not installed" error

Install OrbStack from https://orbstack.dev/

### "Machine did not become ready" timeout

Increase timeout in `test_machine_creation.py` or check OrbStack performance

### Import errors

Ensure you're running from project root and test dependencies are installed:

```bash
pip install -e ".[dev,test]"
```

### ModuleNotFoundError: No module named 'orbstack_nixos_provision'

This is expected because `orbstack-nixos-provision.py` has a hyphen in the filename. Tests use `import_provision_script()` from `tests/utils.py` to handle this. If you're writing new tests that need to import from the main script, use:

```python
from tests.utils import import_provision_script

def test_something():
    provision_module = import_provision_script()
    get_architecture = provision_module.get_architecture
    # ... use the function
```

### Tests hanging

Check if machines are stuck:

```bash
orb list
```

Kill hanging VMs:

```bash
orb delete -f <machine-name>
```

## Contributing

When adding new tests:

1. Follow existing test patterns
2. Use appropriate markers
3. Ensure proper cleanup
4. Add documentation to this README
5. Test locally before committing
