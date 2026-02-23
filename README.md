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
   chmod +x provision-orbstack.py
   ./provision-orbstack.py create my-machine
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
   ./provision-orbstack.py nixos-rebuild my-machine
   ```

### Future Updates

You can update the system configuration using:

- **From the host:**
  ```bash
  ./provision-orbstack.py nixos-rebuild my-machine
  ```

- **From inside the machine:**
  ```bash
  sudo nixos-rebuild switch --flake /etc/nixos#default --impure
  ```

- **Using Colmena** (for managing multiple machines):
  Configure Colmena to target your OrbStack machines via SSH.
