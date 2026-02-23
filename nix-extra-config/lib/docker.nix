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
  # Add this line to your own Nix configuration (specified with `--nix-extra-config <file.nix>`)
  # users.extraGroups.docker.members = [ ];
}
