{ config, pkgs, lib, hostname, modulesPath, ... }:

let
  # Use provided hostname or fall back to "nixos"
  actualHostname = if hostname != "" then hostname else "nixos";
in
{
  imports = [
    (modulesPath + "/profiles/qemu-guest.nix")
  ];

  # System configuration
  system.stateVersion = "24.05";

  # Networking
  networking = {
    hostName = actualHostname;
    useDHCP = lib.mkDefault true;
    firewall.enable = true;
  };

  # Enable Nix flakes
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # Boot loader (OrbStack doesn't use traditional bootloader)
  boot.loader.grub.enable = false;

  # Filesystem configuration for OrbStack
  fileSystems."/" = {
    device = "/dev/vdb1";
    fsType = "auto";
  };

  # SSH daemon
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "yes";
      PasswordAuthentication = true;
    };
  };

  # Essential packages
  environment.systemPackages = with pkgs; [
    vim
    git
    curl
    wget
    htop
  ];

  # Default shell utilities
  programs.bash.enableCompletion = true;

  # Users
  users.users.root.initialPassword = "nixos";

  # Time zone
  time.timeZone = lib.mkDefault "UTC";

  # Locale
  i18n.defaultLocale = "en_US.UTF-8";
}
