# This file allows building and running the software with the Nix package
# manager, used in NixOS or on another distribution.

{
  description = "a Quake3/XreaL/Daemon shader files generator from directories of texture maps";

  inputs = {
    nixpkgs.url = "flake:nixpkgs";
  };

  outputs = { self, nixpkgs }:
    let
      lib = nixpkgs.legacyPackages.x86_64-linux.lib;
    in {

      defaultPackage = lib.mapAttrs (system: pkgs:
        pkgs.python3.pkgs.buildPythonPackage {
          name = "sloth";

          src = pkgs.lib.cleanSource ./.;

          format = "other";

          buildInputs = [
            (pkgs.python3.withPackages (ps: [ ps.pillow ]))
          ];

          installPhase = ''
            runHook preInstall
            install -Dm0755 sloth.py $out/bin/sloth;
            runHook postInstall
          '';

          meta.license = pkgs.lib.licenses.gpl3Plus;
        }
      ) nixpkgs.legacyPackages;

      defaultApp = lib.mapAttrs (system: pkgs:
        { type = "app";
          program = "${self.defaultPackage."${system}"}/bin/sloth";
        }
      ) nixpkgs.legacyPackages;

    };
}
