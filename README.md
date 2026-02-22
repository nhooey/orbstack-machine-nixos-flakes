# OrbStack NixOS Bootstrap

One-command provisioning of NixOS machines in OrbStack from a Git repository.

## Usage

### Initial Provisioning

1. Clone this repository:
   ```bash
   git clone https://github.com/nhooey/orbstack-nixos-bootstrap.git
   cd orbstack-nixos-bootstrap
   ```

2. Run the provisioning script:
   ```bash
   chmod +x provision-orbstack.sh
   ./provision-orbstack.sh my-machine
   ```

3. Connect to your machine:
   ```bash
   orb ssh my-machine
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
   orb -m my-machine nixos-rebuild switch --flake github:nhooey/orbstack-nixos-bootstrap#default
   ```

### Future Updates

You can update the system configuration using:

- **From the host:**
  ```bash
  orb -m my-machine nixos-rebuild switch --flake github:nhooey/orbstack-nixos-bootstrap#default
  ```

- **From inside the machine:**
  ```bash
  nixos-rebuild switch --flake github:nhooey/orbstack-nixos-bootstrap#default
  ```

- **Using Colmena** (for managing multiple machines):
  Configure Colmena to target your OrbStack machines via SSH.
