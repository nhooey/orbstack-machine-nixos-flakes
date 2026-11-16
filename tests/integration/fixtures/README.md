# Test Fixtures

This directory contains test fixtures for the OrbStack NixOS provisioning integration tests.

## Note on Sample Configs

Sample configuration files are dynamically generated in `conftest.py` using pytest's `tmp_path_factory` to ensure test
isolation and avoid filesystem conflicts.

The following sample configs are created at test runtime:

- **simple.nix**: Adds basic packages (tmux)
- **with-service.nix**: Adds packages and a marker file to verify config application
- **docker-user.nix**: Adds user to a docker group
- **invalid.nix**: Contains syntax errors for testing error handling

These are available through the `sample_configs_dir` pytest fixture.
