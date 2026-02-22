{
  description = "OrbStack NixOS Bootstrap";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
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
          ];

          # Note: We use impure evaluation (builtins.getEnv) ONLY during initial bootstrap
          # to accept runtime parameters like hostname. After the first build, these values
          # are embedded in the system configuration and can be changed by editing the Nix files.
          specialArgs = {
            # Read hostname from environment, falling back to "nixos"
            hostname = builtins.getEnv "NIXOS_HOSTNAME";
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
    };
}
