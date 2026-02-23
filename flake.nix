{
  description = "OrbStack NixOS Provision";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    let
      # Helper to build NixOS configuration for a given system
      mkSystem = system:
        nixpkgs.lib.nixosSystem {
          inherit system;

          modules = [
            ./configuration.nix

            # Optionally import user-extra.nix if it exists in the repo
            # This allows users to add custom packages/services without modifying core files
            ({ lib, ... }: {
              imports = lib.optional (builtins.pathExists ./user-extra.nix) ./user-extra.nix;
            })

            # Support for user-specified config file via NIXOS_EXTRA_CONFIG environment variable
            # This allows users to supplement the configuration without forking or modifying files
            # Usage: NIXOS_EXTRA_CONFIG=/path/to/config.nix nixos-rebuild switch --flake .#config --impure
            ({ lib, ... }:
              let
                userConfigPath = builtins.getEnv "NIXOS_EXTRA_CONFIG";
              in {
                imports = lib.optional (userConfigPath != "" && builtins.pathExists userConfigPath) userConfigPath;
              })
          ];

          # Note: We use impure evaluation (builtins.getEnv) ONLY during initial provisioning
          # to accept runtime parameters like hostname and username. After the first build, these values
          # are embedded in the system configuration and can be changed by editing the Nix files.
          specialArgs = {
            hostname = builtins.getEnv "NIXOS_HOSTNAME";
            username = builtins.getEnv "NIXOS_USERNAME";
          };
        };
    in
    {
      nixosConfigurations = {
        # Default configuration for aarch64 (Apple Silicon)
        default = mkSystem "aarch64-linux";

        # x86_64 configuration
        x86_64 = mkSystem "x86_64-linux";
      };
    } // flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        # Development shell for working on this project
        devShells.default = pkgs.mkShell {
          name = "orbstack-nixos-provision";

          buildInputs = with pkgs; [
            # Python and dependencies
            python3
            python3Packages.pip
            python3Packages.black
            python3Packages.mypy

            # Tools for testing and development
            nixos-rebuild
            git

            # Bash for bootstrap script
            bash
          ];

          shellHook = ''
            echo "OrbStack NixOS Provisioning Development Environment"
            echo "=================================================="
            echo "Available commands:"
            echo "  - python3: Python interpreter"
            echo "  - black: Python code formatter"
            echo "  - mypy: Python type checker"
            echo "  - nixos-rebuild: NixOS system builder"
            echo ""
            echo "Run the provisioner:"
            echo "  ./provision-orbstack.py --help"
            echo ""
          '';
        };
      });
}
