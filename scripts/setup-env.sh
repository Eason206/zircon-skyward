#!/usr/bin/env bash
set -euo pipefail
SKYWARD_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export SKYWARD_ROOT
source "$SKYWARD_ROOT/scripts/env.sh"
cd "$SKYWARD_ROOT"

for tool in rustup cargo lz4; do
    command -v "$tool" >/dev/null || { printf 'Missing tool: %s\n' "$tool" >&2; exit 1; }
done
if ! rustup run 1.100.0 rustc --version >/dev/null 2>&1; then
    rustup toolchain install 1.100.0 --profile minimal --component clippy --target aarch64-linux-android
fi
if ! rustup target list --installed --toolchain 1.100.0 | rg -q '^aarch64-linux-android$'; then
    rustup target add --toolchain 1.100.0 aarch64-linux-android
fi
if [ "$(cargo ndk --version 2>/dev/null || true)" != 'cargo-ndk 4.1.2' ]; then
    cargo install cargo-ndk --version 4.1.2 --locked
fi
case $(uname -s) in
    Darwin) skyward_host=darwin-x86_64 ;;
    Linux) skyward_host=linux-x86_64 ;;
    *) printf '%s\n' 'Use a macOS or Linux build host.' >&2; exit 1 ;;
esac
skyward_clang="$ANDROID_NDK_HOME/toolchains/llvm/prebuilt/$skyward_host/bin/aarch64-linux-android${SKYWARD_API}-clang"
test -x "$skyward_clang"
rustup run 1.100.0 rustc --version
cargo ndk --version
"$skyward_clang" --version
"$SKYWARD_PYTHON" --version
printf 'ANDROID_NDK_HOME=%s\nAndroid target: aarch64-linux-android, API %s\n' "$ANDROID_NDK_HOME" "$SKYWARD_API"
printf '%s\n' 'Environment ready. For manual commands: source scripts/env.sh'
