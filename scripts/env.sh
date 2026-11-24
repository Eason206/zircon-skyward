#!/usr/bin/env bash
# Source this file from the repository, in bash or zsh.
export SKYWARD_ROOT="${SKYWARD_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null)}"
export PATH="$HOME/.cargo/bin:$PATH"

if [ ! -f "$SKYWARD_ROOT/rust-toolchain.toml" ]; then
    printf '%s\n' 'Run this from the Skyward checkout, or set SKYWARD_ROOT.' >&2
    return 1 2>/dev/null || exit 1
fi

if [ -z "${ANDROID_NDK_HOME:-}" ]; then
    for skyward_ndk_candidate in \
        "${ANDROID_NDK_ROOT:-}" \
        "$SKYWARD_ROOT/.tools/android-ndk-r29" \
        "$HOME/android-ndk/android-ndk-r29" \
        "$HOME/Library/Android/sdk/ndk/29.0.14206865" \
        "$HOME/Android/Sdk/ndk/29.0.14206865"; do
        if [ -f "$skyward_ndk_candidate/source.properties" ]; then
            export ANDROID_NDK_HOME="$skyward_ndk_candidate"
            break
        fi
    done
    unset skyward_ndk_candidate
fi

if [ ! -f "${ANDROID_NDK_HOME:-}/source.properties" ] || \
    ! rg -q '^Pkg.Revision = 29\.0\.14206865$' "$ANDROID_NDK_HOME/source.properties"; then
    printf '%s\n' 'Set ANDROID_NDK_HOME to Android NDK r29 (29.0.14206865).' >&2
    return 1 2>/dev/null || exit 1
fi

if [ -z "${SKYWARD_PYTHON:-}" ]; then
    for skyward_python_candidate in python3.11 python3.15 python3; do
        if command -v "$skyward_python_candidate" >/dev/null 2>&1 && \
            "$skyward_python_candidate" -c 'import tomllib' >/dev/null 2>&1; then
            export SKYWARD_PYTHON="$skyward_python_candidate"
            break
        fi
    done
    unset skyward_python_candidate
fi
if [ -z "${SKYWARD_PYTHON:-}" ]; then
    printf '%s\n' 'Python 3.11 or later is required for the image verifier.' >&2
    return 1 2>/dev/null || exit 1
fi
export SKYWARD_API=30
