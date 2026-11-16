# Tests for OrbStack NixOS Provisioning

- `tests/unit/` tests the provisioning script's pure functions: architecture mapping, the flake attribute for
  each architecture, `orb list` parsing, path decisions, the bootstrap exports and the command line. They need no
  OrbStack, and `nix flake check` runs them. Run them alone with `dev test --unit`.
- `tests/integration/` creates, provisions and deletes real OrbStack Machines. These tests are skipped when `orb`
  isn't on `PATH`.

## Prerequisites

1. **OrbStack** must be installed and running, for the integration tests
2. **Python 3.9+** required
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
├── __init__.py
├── provision_module.py                  # Loads the provisioning script as a module
├── unit/                                # Pure-function tests, no OrbStack
│   ├── test_architecture.py             # Architecture mapping and flake attributes
│   ├── test_bootstrap_env.py            # Exports passed to bootstrap-nixos.sh
│   ├── test_cli.py                      # Argument parsing and defaults
│   ├── test_orb_list.py                 # Machine states from `orb list`
│   └── test_paths.py                    # Extra-config paths and directories
└── integration/                         # Tests that create real machines
    ├── conftest.py                      # Fixtures, and the skip without OrbStack
    ├── utils.py                         # Machine helpers
    ├── fixtures/
    │   └── README.md
    ├── test_machine_creation.py         # Machine creation tests
    ├── test_nix_flakes.py               # Nix flakes integration tests
    ├── test_extra_config.py             # --extra-config functionality tests
    ├── test_nix_extra_config_dir.py     # orbstack-nix-config/extra directory tests
    ├── test_architecture.py             # Architecture a machine runs and is built for
    └── test_e2e.py                      # End-to-end workflow tests
```

## Running Tests

### Run all tests

```bash
pytest
```

### Run only the unit tests

```bash
dev test --unit  # pytest tests/unit
```

### Run a specific test file

```bash
pytest tests/integration/test_machine_creation.py
```

### Run a specific test

```bash
pytest tests/integration/test_machine_creation.py::test_019_create_machine_default_settings
```

### Skip slow tests

```bash
dev test --fast  # pytest -m "not slow"
```

Every integration test that needs a provisioned machine is marked slow, so this runs the unit tests and
`test_034`, which needs OrbStack but creates no machine.

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

## Integration Test Categories

### Machine Creation Tests (`test_machine_creation.py`)

Tests basic machine creation and management:

- Default settings
- Custom hostname/username
- Machine already exists error handling
- `--recreate` flag functionality

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
- Marker file verification, which shows `NIXOS_EXTRA_CONFIG` reached the flake
- Relative and absolute paths
- Integration with `orbstack-nix-config/extra/lib/` files

### Nix Extra Config Directory Tests (`test_nix_extra_config_dir.py`)

Tests `orbstack-nix-config/extra/` directory copying:

- Directory recursively copied to VM
- Nested structure preservation
- File content verification
- Recopy on rebuild
- Multiple files handling
- Works without a directory

### Architecture Tests (`test_architecture.py`)

Tests the architecture a machine runs, and the one its NixOS system (`/run/current-system/system`) is built for:

- Auto-detection of host architecture
- Explicit ARM architecture flags (aarch64, arm64), skipped on an x86_64 host
- Explicit x86 architecture flags (x86_64, amd64)

The mapping itself, invalid architectures and the flake attribute choice are unit-tested in
`tests/unit/test_architecture.py`.

### End-to-End Tests (`test_e2e.py`)

Complete workflow tests:

- Full create → verify → rebuild → delete workflow
- Multiple sequential rebuilds (idempotency)
- OpenSSH enabled by `configuration.nix`
- Docker workflow

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
3. **Skip if no OrbStack**: The integration tests are skipped if OrbStack is not installed
4. **Isolated configs**: Sample configs generated in temporary directories

## Debugging Failed Tests

### Check test output

```bash
pytest -v -s
```

### Run a single failing test

```bash
pytest tests/integration/test_file.py::test_name -v -s
```

### Check machine state

If a test fails, the machine may still exist:

```bash
orb list
```

### Manually clean up test machines

```bash
dev cleanup  # from the Nix dev shell; --dry-run lists them
```

### Increase timeout for slow environments

Edit `pytest.ini` and increase the `timeout` value.

## Writing New Tests

Put a decision the script makes into a pure function and test it in `tests/unit/`, with no machine. Write an
integration test only for behaviour that needs a real machine:

1. Import necessary utilities from `tests/integration/utils.py`
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
2. Tests may take 10–30 minutes to complete
3. `nix flake check` runs the unit tests without OrbStack
4. Use parallel execution: `pytest -n auto`

## Troubleshooting

### "OrbStack not installed" error

Install OrbStack from https://orbstack.dev/

### "Machine did not become ready" timeout

The script waits 60 seconds for a new machine (`max_wait` in `wait_for_machine_ready()` in `orbstack-machine-nixos-flakes.py`). Raise it, or check OrbStack performance

### Import errors

Ensure you're running from the project root and test dependencies are installed:

```bash
pip install -e ".[dev,test]"
```

### ModuleNotFoundError: No module named 'orbstack_nixos_provision'

This is expected because `orbstack-machine-nixos-flakes.py` has a hyphen in the filename. Tests load it with
`tests/provision_module.py`:

```python
from tests.provision_module import load

provision = load()

def test_something():
    assert provision.map_architecture("arm64") == ("arm64", "aarch64")
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
