#!/usr/bin/env bash
# Build every binding against the IN-REPO core, the way AGENTS.md "Binding gates"
# says: append a [patch.crates-io] redirect to the binding's manifest, build, then
# revert the manifest (a trap reverts it even when the build fails).
#
#   bash formal/bindings/build.sh [rust|cabi|node|ruby|java ...]   (default: all)
#
# Cargo artifacts go under $CARGO_TARGET_DIR (default <repo>/target/formal-bindings),
# which is gitignored. Java classes are compiled with javac into the same tree
# rather than through Gradle, because Gradle's build/ and bindings/java/rust/target
# are not gitignored.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-$ROOT/target/formal-bindings}"
targets=("$@"); [ ${#targets[@]} -eq 0 ] && targets=(rust cabi node ruby java)

with_redirect() {   # <manifest> <path to repo root, relative to the manifest> <cmd...>
  local manifest="$1" rel="$2"; shift 2
  cp "$manifest" "$manifest.formal-orig"
  printf '\n[patch.crates-io]\ndisarm = { path = "%s" }\n' "$rel" >> "$manifest"
  local rc=0
  "$@" || rc=$?
  mv -f "$manifest.formal-orig" "$manifest"
  return "$rc"
}

build_rust() { cd "$ROOT/formal/bindings/rust_oracle" && cargo build --release; }
build_cabi() { cd "$ROOT/bindings/cabi" && with_redirect Cargo.toml ../.. cargo build --release; }
build_node() {
  cd "$ROOT/bindings/node"
  [ -d node_modules ] || npm ci
  with_redirect Cargo.toml ../.. npm run build
}
build_ruby() {
  # rbenv installs gem executables in Ruby's bindir, which is not always on PATH.
  PATH="$(ruby -e 'print RbConfig::CONFIG["bindir"]'):$PATH"
  cd "$ROOT/bindings/ruby" && with_redirect Cargo.toml ../.. bundle exec rake compile
}
build_java() {
  cd "$ROOT/bindings/java/rust" && with_redirect Cargo.toml ../../.. cargo build --release
  local out="$CARGO_TARGET_DIR/java-classes"
  rm -rf "$out" && mkdir -p "$out"
  javac -d "$out" $(find "$ROOT/bindings/java/disarm-java/src/main/java" -name '*.java')
  rm -rf "$CARGO_TARGET_DIR/java-runner" && mkdir -p "$CARGO_TARGET_DIR/java-runner"
  javac -cp "$out" -d "$CARGO_TARGET_DIR/java-runner" "$ROOT/formal/bindings/runners/JavaRunner.java"
}

for t in "${targets[@]}"; do
  case "$t" in
    rust|cabi|node|ruby|java) ( "build_$t" ) ;;
    *) echo "unknown target $t" >&2; exit 2 ;;
  esac
done
for m in bindings/cabi bindings/node bindings/ruby bindings/java/rust; do
  if [ -e "$ROOT/$m/Cargo.toml.formal-orig" ] || grep -q '^\[patch\.crates-io\]' "$ROOT/$m/Cargo.toml"; then
    echo "manifest $m/Cargo.toml was not reverted" >&2; exit 1
  fi
done
