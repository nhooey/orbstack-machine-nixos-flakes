# OrbStack Machine NixOS Flakes provisioning

One-command provisioning and maintenance of OrbStack Machines with NixOS and Flakes enabled, from a Git repository.

This supplements the missing functionality of OrbStack's machine provisioning, where OrbStack can only provision a
Machine with NixOS but without Flakes enabled and without the ability to add extra configuration.

## Usage

### Initial Provisioning

1. Clone this repository and cd in to the directory.
2. Run the provisioning script (building only necessary for running tests):
   ```bash
   ./orbstack-machine-nixos-flakes.py create my-machine
   ```

3. Connect to your machine:
   ```bash
   orb --machine my-machine
   ```

### Adding Extra Configuration

To supplement the default Nix configuration in `orbstack-nix-config/flake.nix`, you can specify a single Nix
configuration with the `--extra-config` command-line option added to either the `create` or `nixos-rebuild` commands of
the `orbstack-machine-nixos-flakes.py` script.

This Nix configuration file can live in this repository in the `orbstack-nix-config/extra` directory, and will be
ignored by Git (for convenience, so non-maintainers of this repository can store their Nix configs). But it can also
live anywhere else, even in its own separate repository.

See example configurations in `orbstack-nix-config/extra/examples/`.

Create or modify an OrbStack Machine with NixOS Flakes enabled, with user-specified extra Nix configuration:

```bash
# Creating a new machine:
./orbstack-machine-nixos-flakes.py create        'my-machine' --extra-config 'orbstack-nix-config/extra/extra.nix'

# Updating an existing machine:
./orbstack-machine-nixos-flakes.py nixos-rebuild 'my-machine' --extra-config 'orbstack-nix-config/extra/extra.nix'
```

### Future Updates

You can update the system configuration using:

- **From the host:**
  ```bash
  ./orbstack-machine-nixos-flakes.py nixos-rebuild my-machine
  ```

- **From inside the machine:**
  ```bash
  sudo nixos-rebuild switch --flake /etc/nixos#default --impure
  ```

- **Using Colmena** (for managing multiple machines):
  Configure Colmena to target your OrbStack machines via SSH.

## Development

### Using Nix Development Shell (Recommended)

The project includes a Nix flake with a complete development environment:

```bash
# Enter the development shell
nix develop
```

All Python dependencies (pytest, black, mypy, etc.) are automatically available in the Nix shell.

### Using pip

If you're not using Nix, install dependencies with pip:

```bash
# Install development and test dependencies
pip install -e ".[dev,test]"

# Run tests
pytest

# Run fast tests only
pytest -m "not slow"
```

### Running Tests

Tests are located in the `tests/` directory. See [tests/README.md](tests/README.md) for detailed testing documentation.

```bash
# Run all tests
pytest

# Run fast tests (skip machine creation)
pytest -m "not slow"

# Run specific test file
pytest tests/test_extra_config.py

# Run with coverage
pytest --cov=provision_orbstack --cov-report=html
```

### Dependencies

All Python dependencies are managed in `pyproject.toml`:

- **Development tools**: black, mypy
- **Testing tools**: pytest, pytest-timeout, pytest-xdist, pytest-cov, pytest-sugar

When using the Nix development shell, all dependencies are automatically provided without needing pip.
