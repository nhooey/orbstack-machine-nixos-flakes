{ config, pkgs, ... }:

{
  # Enable Docker
  virtualisation.docker.enable = true;

  # Install Docker-related packages
  environment.systemPackages = with pkgs; [
    docker
    docker-compose
  ];

  # To ensure your specified user can use Docker without invoking `sudo`:
  # Add this line to your own Nix configuration (specified with `--orbstack-nix-config/extra <file.nix>`)
  # users.extraGroups.docker.members = [ ];
}
