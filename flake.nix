{
  description = "OrbStack NixOS Provisioning Tool - Development Environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.11";
    flake-utils.url = "github:numtide/flake-utils";
    devshell.url = "github:numtide/devshell";
    devshell.inputs.nixpkgs.follows = "nixpkgs";
    pyproject-nix.url = "github:nix-community/pyproject.nix";
    pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, devshell, pyproject-nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python3;

        # Load pyproject.toml
        project = pyproject-nix.lib.project.loadPyproject {
          projectRoot = ./.;
        };

        # Create Python environment with all dependencies from pyproject.toml
        pythonEnv = python.withPackages (ps:
          # Get base dependencies plus dev and test extras
          (project.renderers.withPackages {
            inherit python;
            extras = ["dev" "test"];
          }) ps
        );
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

            # Tools for testing and development
            pkgs.nixos-rebuild
            pkgs.git
            pkgs.bash
          ];

          devshell.startup.symlinkNixTools = {
            text = ''
              # Create .nix-tools directory for PyCharm/IDE configuration
              NIX_TOOLS_DIR="$PRJ_ROOT/.nix"
              mkdir -p "$NIX_TOOLS_DIR"

              # Symlink bin directory from Python environment
              ln -sf "${pythonEnv}" "$NIX_TOOLS_DIR/python"

              echo "Symlinked Nix tools to '$NIX_TOOLS_DIR'"
              echo "Configure PyCharm Python interpreter to: $NIX_TOOLS_DIR/bin/python"
            '';
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
              command = "orb list | grep -E '^test-.*-[0-9]{13}' | awk '{print $1}' | xargs -I {} orb delete -f {}";
            }
          ];
        };
      });
}
