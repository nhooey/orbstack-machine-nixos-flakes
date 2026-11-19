{
  description = "orbstack-machine-nixos-flakes dev-shell skill set, a sub-flake the root dev shell runs on `nix develop`, never a root input, so the skill sources live only in this flake's lock.";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    systems.url = "github:nix-systems/default";

    # The builder lib; it carries no skill inputs.
    agent-skill-flake = {
      url = "github:nhooey/agent-skill-flake";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # skillspkgs' skill combinations, one per repository family. This
    # repository is in the Nix tooling family and takes its combination.
    skillspkgs-combinations = {
      url = "github:nhooey/skillspkgs?dir=sources/combinations";
      inputs.nixpkgs.follows = "nixpkgs";
      inputs.python-skills.follows = "python-skills";
    };

    # The one addition beyond the combination; see `sources` below.
    python-skills = {
      url = "github:nhooey/python-skills";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      nixpkgs,
      agent-skill-flake,
      ...
    }@inputs:
    agent-skill-flake.lib.mkDevshellSkillsFlake {
      inherit nixpkgs;
      systems = import inputs.systems;
      name = "orbstack-machine-nixos-flakes-devshell";
      sources = [
        # The Nix tooling family's skills.
        { source = inputs.skillspkgs-combinations.combinations.nix-tooling; }
        # This repository is Python-first, unlike the rest of its family: the
        # provisioning script, `tools/dev.py` and the tests are Python.
        {
          source = inputs.python-skills;
          skills = [ "python-hygiene-functional-style" ];
        }
      ];
    };
}
