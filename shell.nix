# This is a Nix shell file
#
# If you're on NixOS (or use Nix package manager) and want to quickly set up
# a local development environment, just run `nix-shell` and you'll be set.
#
# A local virtualenv will be created, but Docker Compose is also available.

with import <nixpkgs> {}; {
  devEnv = stdenv.mkDerivation {
    name = "dev";
    buildInputs = [ stdenv python36 python36Packages.virtualenv python36Packages.docker_compose postgresql git ];

    LDFLAGS="-L${pkgs.postgresql.lib}/lib";
    CFLAGS="-I${pkgs.postgresql}/include";

    shellHook = ''
      unset SOURCE_DATE_EPOCH
      export PYTHONPATH="$(pwd)"

      if [ ! -d .virtualenv ]; then
        virtualenv --python=python3.6 .virtualenv
        .virtualenv/bin/pip install -r requirements.dev.txt
      fi
      source .virtualenv/bin/activate

      export DEBUG=true
    '';
  };
}
