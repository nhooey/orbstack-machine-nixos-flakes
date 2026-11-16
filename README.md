# OrbStack Machine NixOS Flakes provisioning

One-command provisioning and maintenance of OrbStack Machines with NixOS and Flakes enabled, from a Git repository.

This supplements the missing functionality of OrbStack's machine provisioning, where OrbStack can only provision a
Machine with NixOS but without Flakes enabled and without the ability to add extra configuration.

## Usage

### Initial Provisioning

1. Clone this repository and cd in to the directory.
2. Enter the dev shell with `nix develop`, and create the machine with `provision`, which runs
   `orbstack-machine-nixos-flakes.py`:
   ```bash
   provision create my-machine
   ```
   Outside the dev shell, run `./orbstack-machine-nixos-flakes.py` with the same arguments; it needs only Python 3.9+.

3. Connect to your machine:
   ```bash
   orb --machine my-machine
   ```

### Adding Extra Configuration

To supplement the default Nix configuration in `orbstack-nix-config/flake.nix`, you can specify a single Nix
configuration with the `--extra-config` command-line option added to either the `create` or `nixos-rebuild` commands of
`provision` (the `orbstack-machine-nixos-flakes.py` script).

This Nix configuration file can live in this repository in the `orbstack-nix-config/extra` directory, and will be
ignored by Git (for convenience, so non-maintainers of this repository can store their Nix configs). But it can also
live anywhere else, even in its own separate repository.

See example configurations in `orbstack-nix-config/extra/examples/`.

Create or modify an OrbStack Machine with NixOS Flakes enabled, with user-specified extra Nix configuration:

```bash
# Creating a new machine:
provision create        'my-machine' --extra-config 'orbstack-nix-config/extra/extra.nix'

# Updating an existing machine:
provision nixos-rebuild 'my-machine' --extra-config 'orbstack-nix-config/extra/extra.nix'
```

### Future Updates

You can update the system configuration using:

- **From the host:**
  ```bash
  provision nixos-rebuild my-machine
  ```

- **From inside the machine:**
  ```bash
  sudo NIXOS_HOSTNAME="$(hostname)" NIXOS_USERNAME="$USER" \
    nixos-rebuild switch --flake /etc/nixos#default --impure
  ```
  The flake reads the hostname and username from these variables on every build, and falls back to `nixos` for
  both when they're unset. Use `#x86_64` in place of `#default` on an x86_64 machine, and add
  `NIXOS_EXTRA_CONFIG=/path/to/extra.nix` to keep an extra configuration.

## Development

### Using Nix Development Shell (Recommended)

The project includes a Nix flake with a complete development environment:

```bash
# Enter the development shell
nix develop
```

All Python dependencies (pytest, black, mypy, etc.) are automatically available in the Nix shell, along with the
two commands its menu lists:

- `provision`: creates or rebuilds a machine, as in [Usage](#usage).
- `dev`: the development commands, `test`, `format`, `typecheck`, `python-files` and `cleanup`. `dev --help` lists
  them, and `dev <command> --help` each one's options.

### Using pip

If you're not using Nix, install dependencies with pip into a virtual environment of your own (the Nix shell has no
`pip`):

```bash
# Install development and test dependencies
pip install -e ".[dev,test]"
```

### Running Tests

Tests are located in the `tests/` directory. See [tests/README.md](tests/README.md) for detailed testing documentation.

```bash
# Run all tests (pytest); the integration tests create real OrbStack Machines
dev test

# Run only the unit tests, which need no OrbStack (nix flake check runs these too)
dev test --unit

# Run the tests not marked slow (pytest -m 'not slow'); none of these creates a machine
dev test --fast

# Run a specific test file; arguments dev test doesn't know go to pytest
dev test tests/integration/test_extra_config.py

# Run with coverage, in parallel, or with output shown as it happens
dev test --coverage
dev test --parallel
dev test --debug

# Delete test machines left behind by an interrupted run (--dry-run lists them)
dev cleanup
```

Outside the Nix shell, run `pytest` directly: `pytest tests/unit` for the unit tests, `pytest -m 'not slow'` for the
fast ones.

### Dependencies

All Python dependencies are managed in `pyproject.toml`:

- **Development tools**: black, mypy
- **Testing tools**: pytest, pytest-timeout, pytest-xdist, pytest-cov, pytest-sugar

When using the Nix development shell, all dependencies are automatically provided without needing pip.
