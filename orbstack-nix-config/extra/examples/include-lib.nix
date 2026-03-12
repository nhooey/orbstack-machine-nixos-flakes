{ config, pkgs, ... }:

{
  imports = [
    ../lib/docker.nix
  ];

  environment.systemPackages = with pkgs; [
    lolcat
  ];
}
