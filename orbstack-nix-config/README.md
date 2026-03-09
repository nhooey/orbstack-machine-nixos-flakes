# OrbStack NixOS Machine Configuration

This directory contains the NixOS configuration for OrbStack machines provisioned by the `orbstack-machine-nixos-flakes.py` tool.

## Structure

```
orbstack-nix-config/
├── flake.nix           # NixOS flake configuration
├── configuration.nix   # Base NixOS system configuration
├── extra/              # Optional extra configurations
│   ├── lib/           # Reusable configuration modules
│   │   └── docker.nix # Docker configuration
│   └── README.md      # Documentation for extra configs
└── README.md          # This file
```

## Files

### `flake.nix`

The main flake defining NixOS configurations for:
- `default` - aarch64-linux (Apple Silicon)
- `x86_64` - x86_64-linux

Supports environment variables for customization:
- `NIXOS_HOSTNAME` - Set hostname during provisioning
- `NIXOS_USERNAME` - Set username during provisioning
- `NIXOS_EXTRA_CONFIG` - Path to additional config file

### `configuration.nix`

Base NixOS system configuration including:
- Essential packages (vim, git, curl, wget, htop)
- SSH daemon configuration
- User configuration with sudo access
- Networking and firewall
- Nix flakes enabled

### `extra/`

Contains optional configuration modules that can be used with `--extra-config`:

#### `extra/lib/docker.nix`
Enables Docker support. Use with:
```bash
./orbstack-machine-nixos-flakes.py create my-machine \
  --extra-config orbstack-nix-config/extra/lib/docker.nix
```

## Usage

### Basic Provisioning

The provisioning script automatically copies this directory to the OrbStack machine at `/etc/nixos/`.

```bash
# Create a machine (uses the flake in `orbstack-nix-config/flake.nix` automatically)
./orbstack-machine-nixos-flakes.py create my-machine
```

### With Extra Configuration

```bash
# Add Docker configuration
./orbstack-machine-nixos-flakes.py create my-machine \
  --extra-config orbstack-nix-config/extra/lib/docker.nix
```

### Custom User Configuration

Create a `user-extra.nix` file in the project root (not in this directory) for your custom settings:

```nix
{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    neovim
    tmux
  ];
}
```

The flake automatically imports `../user-extra.nix` if it exists.

### Manual Rebuilds

From inside the machine:
```bash
sudo nixos-rebuild switch --flake /etc/nixos#default --impure
```

From the host:
```bash
./orbstack-machine-nixos-flakes.py nixos-rebuild my-machine
```

## Customization

### Adding New Configurations

1. Create a new `.nix` file in `extra/lib/`
2. Export the configuration as a module
3. Use it with `--extra-config`

Example (`extra/lib/postgresql.nix`):
```nix
{ config, pkgs, ... }:

{
  services.postgresql = {
    enable = true;
    package = pkgs.postgresql_15;
  };
}
```

### Modifying Base Configuration

Edit `configuration.nix` to change system-wide settings. Changes apply to all new machines.

### Architecture-Specific Configuration

The flake provides separate configurations for different architectures:
- Use `#default` for aarch64 (Apple Silicon)
- Use `#x86_64` for x86_64 systems

The provisioning script selects the appropriate one automatically.

## Development

To test configuration changes without provisioning:
```bash
cd orbstack-nix-config
nix flake check
```

To evaluate a specific configuration:
```bash
nix eval .#nixosConfigurations.default.config.system.build.toplevel
```
