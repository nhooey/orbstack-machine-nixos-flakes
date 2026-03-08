{ config, pkgs, lib, hostname, username, modulesPath, ... }:

let
  # Use provided hostname or fall back to "nixos"
  actualHostname = if hostname != "" then hostname else "nixos";
  # Use provided username or fall back to "nixos"
  actualUsername = if username != "" then username else "nixos";
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
  boot.loader.systemd-boot.enable = false;

  # Filesystem configuration for OrbStack
  fileSystems."/" = {
    device = "/dev/vdb1";
    fsType = "auto";
  };

  # D-Bus - ensure it's properly enabled for systemd services
  services.dbus.enable = true;

  # SSH daemon
  services.openssh = {
    enable = true;
    settings = {
      PermitRootLogin = "yes";
      PasswordAuthentication = true;
    };
  };

  # Disable systemd-hostnamed since it can fail in containerized environments
  # The hostname is still set via /etc/hostname and will be correct after reboot
  # For immediate hostname changes, tests should check /etc/hostname or reboot
  systemd.services.systemd-hostnamed.enable = false;
  systemd.sockets.systemd-hostnamed.enable = false;

  # Essential packages
  environment.systemPackages = with pkgs; [
    vim
    git
    curl
    wget
    htop
  ];

  # Default shell utilities
  programs.bash.completion.enable = true;

  # Users
  users.users.root.initialPassword = "nixos";

  # Create default user matching host username
  # OrbStack expects this user to exist for seamless integration
  users.users.${actualUsername} = {
    isNormalUser = true;
    createHome = true;
    home = "/home/${actualUsername}";
    extraGroups = [ "wheel" "networkmanager" "docker" ];
    initialPassword = "nixos";
    shell = pkgs.bash;
  };

  # Allow wheel group to use sudo without password
  security.sudo.wheelNeedsPassword = false;

  # Preserve NIXOS_* and NIX_* environment variables when using sudo
  # This is needed for nixos-rebuild to receive configuration parameters
  security.sudo.extraConfig = ''
    Defaults env_keep += "NIXOS_HOSTNAME NIXOS_USERNAME NIXOS_EXTRA_CONFIG NIX_CONFIG FLAKE_REF"
  '';

  # Time zone
  time.timeZone = lib.mkDefault "UTC";

  # Locale
  i18n.defaultLocale = "en_US.UTF-8";

  # Fix locale warnings when connecting from macOS
  # macOS passes LC_CTYPE=UTF-8 which is invalid in Linux
  environment.variables = {
    LC_CTYPE = "en_US.UTF-8";
    LC_ALL = "en_US.UTF-8";
  };
}
