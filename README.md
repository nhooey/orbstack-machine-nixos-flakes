# OrbStack NixOS Provision

One-command provisioning of NixOS machines in OrbStack from a Git repository.

## Usage

### Initial Provisioning

1. Clone this repository:
   ```bash
   git clone https://github.com/nhooey/orbstack-nixos-provision.git
   cd orbstack-nixos-provision
   ```

2. Run the provisioning script:
   ```bash
   chmod +x orbstack-nixos-provision.py
   ./orbstack-nixos-provision.py create my-machine
   ```

3. Connect to your machine:
   ```bash
   orb --machine my-machine
   ```

### Adding Custom Configuration

To add your own packages, services, or configuration:

1. Create a file named `user-extra.nix` in the repository root:
   ```nix
   { config, pkgs, ... }:

   {
     environment.systemPackages = with pkgs; [
       neovim
       tmux
       # Add more packages here
     ];

     services.postgresql = {
       enable = true;
       # Add service configuration here
     };

     # Any other NixOS options
   }
   ```

2. The `user-extra.nix` file will be automatically imported during provisioning and all future rebuilds.

3. After creating or modifying `user-extra.nix`, rebuild the system:
   ```bash
   ./orbstack-nixos-provision.py nixos-rebuild my-machine
   ```

### Future Updates

You can update the system configuration using:

- **From the host:**
  ```bash
  ./orbstack-nixos-provision.py nixos-rebuild my-machine
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

# Available commands (run 'menu' to see all):
provision            # Run the provisioning script
tests                # Run all tests
tests-fast           # Run only fast tests (skip slow machine creation)
tests-verbose        # Run tests with verbose output
tests-parallel       # Run tests in parallel
tests-coverage       # Run tests with coverage report
tests-cleanup        # Clean up leftover test machines
format               # Format Python code with black
typecheck            # Run mypy type checker
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
