# orbstack-machine-nixos-flakes

Provisions and maintains OrbStack Machines running NixOS with Flakes enabled. `orbstack-machine-nixos-flakes.py` creates a machine and runs `nixos-rebuild` in it from the NixOS flake in `orbstack-nix-config/`, optionally merging in a user's extra Nix configuration. `bootstrap-nixos.sh` runs inside the machine. Tests live in `tests/`.

## Build and test

- `nix develop`: the dev shell, with Python and its dev and test dependencies from `uv.lock`, the `provision` and `dev` commands, and the project's skills installed into `.agents/skills/` from the `skills-devshell/` sub-flake.
- `provision` runs `orbstack-machine-nixos-flakes.py` from any directory, with its `create` and `nixos-rebuild` commands.
- `dev` (`tools/dev.py`) runs the development commands; `dev --help` lists them and `dev <command> --help` their options.
  - `dev test --unit` runs the unit tests of the script's pure functions, which need no OrbStack. `dev test` runs every test, and `dev test --fast` the ones not marked slow. Arguments `dev test` doesn't know go to pytest. The integration tests in `tests/integration/` need OrbStack, and are skipped without `orb` on `PATH`; running them creates and deletes real OrbStack Machines, and `dev cleanup` deletes any left behind.
  - `dev typecheck` runs mypy on the Python files Git tracks.
  - `dev format` (`nix fmt`, treefmt: black and nixfmt) formats the Python and Nix files.
- `nix flake check`: evaluates the dev shell, runs the unit tests and fails on unformatted files. It can't run the integration tests, which need OrbStack.
