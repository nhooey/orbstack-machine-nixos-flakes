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
  programs.bash.completion.enable = true;

  # Users
  users.users.root.initialPassword = "nixos";

  # Create default user matching host username
  # OrbStack expects this user to exist for seamless integration
  users.users.${actualUsername} = {
    isNormalUser = true;
    extraGroups = [ "wheel" "networkmanager" "docker" ];
    initialPassword = "nixos";
    shell = pkgs.bash;
  };

  # Allow wheel group to use sudo without password
  security.sudo.wheelNeedsPassword = false;

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
