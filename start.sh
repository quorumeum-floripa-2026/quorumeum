#!/usr/bin/env bash
#
# Quorumeum start script
#
# Writes the custom signet config, builds from source if needed,
# and starts the node. Works standalone or via `nix develop`.
#
# Usage:
#   ./start.sh          # build + start node
#   ./start.sh --stop   # stop the node
#   ./start.sh --clean  # remove build and data dirs
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="${QUORUMEUM_BUILD_DIR:-$REPO_DIR/build}"
DATADIR="${QUORUMEUM_DATADIR:-$REPO_DIR/.quorumeum-data}"

SIGNET_CHALLENGE="51208d8dfd7fdc663efe1d54f05182fddddd7cf47ba3ed6e6932eccd41b7722da91b"
SIGNET_SEED_NODE="167.71.167.51"

BITCOIND="$BUILD_DIR/bin/bitcoind"
BITCOIN_CLI="$BUILD_DIR/bin/bitcoin-cli"

cli() {
  "$BITCOIN_CLI" -datadir="$DATADIR" "$@"
}

node_is_running() {
  cli getblockchaininfo &>/dev/null
}

write_config() {
  mkdir -p "$DATADIR"
  cat > "$DATADIR/bitcoin.conf" <<EOF
signet=1

[signet]
signetchallenge=$SIGNET_CHALLENGE
connect=$SIGNET_SEED_NODE
EOF
  echo "==> Config written to $DATADIR/bitcoin.conf"
}

check_deps() {
  local missing=()
  for cmd in cmake pkg-config python3; do
    if ! command -v "$cmd" &>/dev/null; then
      missing+=("$cmd")
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    echo "==> Missing build dependencies: ${missing[*]}"
    echo "    Install them with your package manager, e.g.:"
    echo "      apt install ${missing[*]}       # Debian/Ubuntu"
    echo "      brew install ${missing[*]}      # macOS"
    echo "    Or use 'nix develop' to get everything automatically."
    return 1
  fi
}

build() {
  if [ -f "$BITCOIND" ]; then
    echo "==> Build already exists at $BUILD_DIR. Delete it or run './start.sh --clean' to rebuild."
    return 0
  fi

  check_deps

  echo "==> Configuring Quorumeum..."
  cmake -B "$BUILD_DIR" -S "$REPO_DIR" \
    -DBUILD_GUI=OFF \
    -DWITH_QRENCODE=OFF \
    -DWITH_ZMQ=OFF

  local jobs
  jobs=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
  echo "==> Building with $jobs parallel jobs..."
  cmake --build "$BUILD_DIR" -j"$jobs"

  echo "==> Build complete."
}

start_node() {
  if node_is_running; then
    echo "==> Quorumeum node is already running."
    return 0
  fi

  if [ ! -f "$BITCOIND" ]; then
    echo "==> bitcoind not found at $BITCOIND"
    echo "    Run './start.sh' without flags to build first."
    return 1
  fi

  echo "==> Starting Quorumeum node on custom signet..."
  "$BITCOIND" -datadir="$DATADIR" -daemon

  echo "==> Waiting for node to be ready..."
  for i in $(seq 1 30); do
    if node_is_running; then
      echo "==> Quorumeum node is ready!"
      echo ""
      echo "    qcli getblockchaininfo    # query the node"
      echo "    qcli getpeerinfo          # see connected peers"
      echo "    qcli help                 # list all commands"
      echo "    qcli stop                 # stop the node"
      echo ""
      return 0
    fi
    sleep 1
  done

  echo "==> Node did not become ready within 30s. Check logs at $DATADIR/signet/debug.log"
  return 1
}

stop_node() {
  if node_is_running; then
    echo "==> Stopping Quorumeum node..."
    cli stop
    echo "==> Node stopped."
  else
    echo "==> Node is not running."
  fi
}

clean() {
  stop_node 2>/dev/null || true
  echo "==> Removing build dir: $BUILD_DIR"
  rm -rf "$BUILD_DIR"
  echo "==> Removing data dir: $DATADIR"
  rm -rf "$DATADIR"
  echo "==> Clean complete."
}

setup_qcli() {
  # Create a qcli wrapper script in the build bin dir
  cat > "$BUILD_DIR/bin/qcli" <<WRAPPER
#!/usr/bin/env bash
exec "$BITCOIN_CLI" -datadir="$DATADIR" "\$@"
WRAPPER
  chmod +x "$BUILD_DIR/bin/qcli"
}

case "${1:-}" in
  --stop)
    stop_node
    ;;
  --clean)
    clean
    ;;
  *)
    write_config
    build
    setup_qcli
    start_node
    ;;
esac
