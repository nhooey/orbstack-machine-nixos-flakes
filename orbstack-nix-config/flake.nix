{
  description = "OrbStack NixOS Machine Configuration";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
  };

  outputs = { self, nixpkgs }:
    let
      # Helper to build NixOS configuration for a given system
      mkSystem = system:
        nixpkgs.lib.nixosSystem {
          inherit system;

          modules = [
            ./configuration.nix

            # Support for user-specified config file via NIXOS_EXTRA_CONFIG environment variable
            # This allows users to supplement the configuration without forking or modifying files
            # Usage: NIXOS_EXTRA_CONFIG=/path/to/config.nix nixos-rebuild switch --flake .#config --impure
            ({ lib, ... }:
              let
                userConfigPath = builtins.getEnv "NIXOS_EXTRA_CONFIG";
              in
              {
                imports = lib.optional (userConfigPath != "" && builtins.pathExists userConfigPath) userConfigPath;
              })
          ];

          # Impure evaluation (builtins.getEnv) takes the hostname and username at build time.
          # Every build reads them again, so a rebuild without NIXOS_HOSTNAME and NIXOS_USERNAME
          # set falls back to "nixos" for both (see configuration.nix).
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
    };
}
