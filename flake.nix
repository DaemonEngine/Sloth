# This file allows building and running the software with the Nix package
# manager, used in NixOS or on another distribution.

{
  description = "a Quake3/XreaL/Daemon shader files generator from directories of texture maps";

  inputs = {
    nixpkgs.url = "flake:nixpkgs";
  };

  outputs = { self, nixpkgs }:
    let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
    in {

      defaultPackage.x86_64-linux =
        pkgs.python310.pkgs.buildPythonPackage {
          name = "sloth";

          src = pkgs.lib.cleanSource ./.;

          format = "other";

          buildInputs = [
            (pkgs.python310.withPackages (ps: [ ps.pillow ]))
          ];

          installPhase = ''
            runHook preInstall
            install -Dm0755 sloth.py $out/bin/sloth;
            runHook postInstall
          '';

          meta.license = pkgs.lib.licenses.gpl3Plus;
        };

      defaultApp.x86_64-linux = {
        type = "app";
        program = "${self.defaultPackage.x86_64-linux}/bin/sloth";
      };

    };
}
