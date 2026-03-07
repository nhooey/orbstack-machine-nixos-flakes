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

            # Optionally import user-extra.nix if it exists in the parent directory
            # This allows users to add custom packages/services without modifying core files
            ({ lib, ... }: {
              imports = lib.optional (builtins.pathExists ../user-extra.nix) ../user-extra.nix;
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
          specialArgs =
            let
              hostnameEnv = builtins.getEnv "NIXOS_HOSTNAME";
              usernameEnv = builtins.getEnv "NIXOS_USERNAME";
              # Debug: Print environment variables during evaluation
              _ = builtins.trace "[FLAKE DEBUG] NIXOS_HOSTNAME=${hostnameEnv} NIXOS_USERNAME=${usernameEnv}" null;
            in {
              hostname = hostnameEnv;
              username = usernameEnv;
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
