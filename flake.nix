{
  description = "OrbStack NixOS Provisioning Tool - Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
    devshell.url = "github:numtide/devshell";
    devshell.inputs.nixpkgs.follows = "nixpkgs";
    pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
    uv2nix.url = "github:pyproject-nix/uv2nix";
    uv2nix.inputs.pyproject-nix.follows = "pyproject-nix";
    uv2nix.inputs.nixpkgs.follows = "nixpkgs";
    pyproject-build-systems.url = "github:pyproject-nix/build-system-pkgs";
    pyproject-build-systems.inputs.pyproject-nix.follows = "pyproject-nix";
    pyproject-build-systems.inputs.uv2nix.follows = "uv2nix";
    pyproject-build-systems.inputs.nixpkgs.follows = "nixpkgs";
    # The builder lib for the dev shell's skills, not a skill: its
    # `devshellSkillsHook` runs the `skills-devshell/` sub-flake on
    # `nix develop`, so this flake carries no skill inputs.
    agent-skill-flake.url = "github:nhooey/agent-skill-flake";
    agent-skill-flake.inputs.nixpkgs.follows = "nixpkgs";
    agent-skill-flake.inputs.devshell.follows = "devshell";
    treefmt-nix.url = "github:numtide/treefmt-nix";
    treefmt-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
      devshell,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      agent-skill-flake,
      treefmt-nix,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;

        # Load uv workspace from uv.lock
        workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };

        # Create overlay from workspace
        overlay = workspace.mkPyprojectOverlay {
          sourcePreference = "wheel";
        };

        # Create base Python package set
        baseSet = pkgs.callPackage pyproject-nix.build.packages {
          inherit python;
        };

        # Apply overlays (build systems + workspace dependencies)
        pythonSet = baseSet.overrideScope (
          pkgs.lib.composeManyExtensions [
            pyproject-build-systems.overlays.default
            overlay
          ]
        );

        # Create virtual environment with all dependencies (including dev and test)
        pythonEnv = pythonSet.mkVirtualEnv "orbstack-machine-nixos-flakes-env" workspace.deps.all;

        # Installs the skills in `skills-devshell/` into `.agents/skills/` on
        # `nix develop`, and adds the `skills` commands.
        devshellSkills = agent-skill-flake.lib.devshellSkillsHook { };

        # `nix fmt` formats the Python and Nix files; `nix flake check` fails on
        # any file it would change.
        treefmt = treefmt-nix.lib.evalModule pkgs {
          projectRootFile = "flake.nix";
          programs.black.enable = true;
          programs.nixfmt.enable = true;
        };
      in
      {
        formatter = treefmt.config.build.wrapper;
        checks.formatting = treefmt.config.build.check self;

        # The unit tests, which need no OrbStack. The integration tests in
        # `tests/integration/` create real machines, so they run only from the
        # dev shell.
        checks.unit-tests =
          pkgs.runCommand "orbstack-machine-nixos-flakes-unit-tests"
            {
              nativeBuildInputs = [
                pythonEnv
                pkgs.bash
              ];
              src = pkgs.lib.fileset.toSource {
                root = ./.;
                fileset = pkgs.lib.fileset.unions [
                  ./orbstack-machine-nixos-flakes.py
                  ./orbstack-nix-config/flake.nix
                  ./pytest.ini
                  ./tests
                  ./tools
                ];
              };
              PYTHONDONTWRITEBYTECODE = "1";
            }
            ''
              cp -r "$src" source
              chmod -R u+w source
              cd source
              pytest tests/unit -p no:cacheprovider
              touch "$out"
            '';

        # Development shell for working on this project
        devShells.default = devshell.legacyPackages.${system}.mkShell {
          name = "orbstack-machine-nixos-flakes";

          motd = ''
            {202}🚀 OrbStack NixOS Provisioning Development Environment{reset}
            $(type -p menu &>/dev/null && menu)
          '';

          packages = [
            # Python environment with all dependencies
            pythonEnv

            # uv for package management
            pkgs.uv

            # Tools for testing and development
            pkgs.nixos-rebuild
            pkgs.git
            pkgs.bash
          ];

          devshell.startup = {
            install-skills.text = devshellSkills.startup;
            alias-ls = {
              text = "alias ls='ls --color=always'";
            };
            symlink-python-env = {
              text = ''
                # Create .venv symlink pointing to the Nix-provided Python environment
                NIX_TOOLS_DIR="$PRJ_ROOT/.nix"
                mkdir -p "$NIX_TOOLS_DIR"
                VENV_DIR="$NIX_TOOLS_DIR/venv"
                TARGET_ENV="${pythonEnv}"

                # Only recreate if it doesn't exist or points to the wrong location
                if [ ! -L "$VENV_DIR" ] || [ "$(readlink "$VENV_DIR")" != "$TARGET_ENV" ]; then
                  echo "Symlinking Python environment to: '$VENV_DIR'"
                  rm -f "$VENV_DIR"
                  ln -s "$TARGET_ENV" "$VENV_DIR"
                fi
              '';
            };
          };

          commands = devshellSkills.commands ++ [
            {
              category = "app";
              name = "provision";
              help = "Create an OrbStack NixOS machine or rebuild one (create, nixos-rebuild)";
              command = ''exec "$PRJ_ROOT/orbstack-machine-nixos-flakes.py" "$@"'';
            }
            {
              category = "code";
              name = "dev";
              help = "Run the tests, format, type-check or clean up test machines (dev --help)";
              command = ''exec python "$PRJ_ROOT/tools/dev.py" "$@"'';
            }
          ];
        };
      }
    );
}
