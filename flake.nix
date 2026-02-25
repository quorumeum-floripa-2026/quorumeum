{
  description = "Quorumeum - Bitcoin Core fork";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        devShells.default = pkgs.mkShell {
          nativeBuildInputs = with pkgs; [
            cmake
            pkg-config
            python3
            hexdump
          ];

          buildInputs = with pkgs; [
            boost
            libevent
            sqlite
            zeromq
            zlib
            capnproto
            miniupnpc
            libnatpmp
          ] ++ pkgs.lib.optionals pkgs.stdenv.isLinux [
            qt6.qtbase
            qt6.qttools
            qrencode
          ];

          shellHook = ''
            bash "$PWD/start.sh"
            export PATH="$PWD/build/bin:$PATH"
          '';
        };

        packages.default = pkgs.stdenv.mkDerivation {
          pname = "quorumeum";
          version = "30.2.0";

          src = self;

          nativeBuildInputs = with pkgs; [
            cmake
            pkg-config
            python3
            hexdump
          ];

          buildInputs = with pkgs; [
            boost
            libevent
            sqlite
            zeromq
            zlib
            capnproto
            miniupnpc
            libnatpmp
          ];

          cmakeFlags = [
            "-DBUILD_GUI=OFF"
            "-DWITH_QRENCODE=OFF"
          ];

          meta = with pkgs.lib; {
            description = "Quorumeum node";
            license = licenses.mit;
            platforms = platforms.unix;
          };
        };
      }
    );
}
