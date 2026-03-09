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
  };

  outputs = { self, nixpkgs, flake-utils, devshell, pyproject-nix, uv2nix, pyproject-build-systems }:
    flake-utils.lib.eachDefaultSystem (system:
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
      in
      {
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

          commands = [
            {
              category = "app";
              name = "provision";
              help = "Run the provisioning script";
              command = ''./orbstack-machine-nixos-flakes.py "$@"'';
            }
            {
              category = "code";
              name = "python-source-files";
              help = "List Python source files in the project";
              command = "git ls-files | egrep '\.py$'";
            }
            {
              category = "code";
              name = "format";
              help = "Format Python code with black";
              command = ''black $(python-source-files) tests/ "$@"'';
            }
            {
              category = "code";
              name = "typecheck";
              help = "Run mypy type checker";
              command = ''mypy $(python-source-files) "$@"'';
            }
            {
              category = "testing";
              name = "tests";
              help = "Run all tests";
              command = ''pytest "$@"'';
            }
            {
              category = "testing";
              name = "tests-fast";
              help = "Run only fast tests (skip slow machine creation tests)";
              command = ''pytest -m 'not slow' "$@"'';
            }
            {
              category = "testing";
              name = "tests-verbose";
              help = "Run tests with verbose output";
              command = ''pytest -v "$@"'';
            }
            {
              category = "testing";
              name = "tests-debug";
              help = "Run tests with real-time output (no capture)";
              command = ''pytest -s -vv "$@"'';
            }
            {
              category = "testing";
              name = "tests-parallel";
              help = "Run tests in parallel";
              command = ''pytest -n auto "$@"'';
            }
            {
              category = "testing";
              name = "tests-coverage";
              help = "Run tests with coverage report";
              command = ''pytest --cov=provision_orbstack --cov-report=html --cov-report=term "$@"'';
            }
            {
              category = "testing";
              name = "tests-cleanup";
              help = "Clean up leftover test machines";
              command = ''
                machines=$(orb list | grep -E '^test-nixos-[0-9]{13}-*' | awk '{print $1}')
                if [ -n "$machines" ]; then
                  echo "Deleting the following OrbStack Machines:"
                  echo "$machines" | sed 's/^/  /'
                  echo "$machines" | xargs -I {} orb delete -f {}
                else
                  echo "No test machines to clean up."
                fi
              '';
            }
          ];
        };
      });
}
