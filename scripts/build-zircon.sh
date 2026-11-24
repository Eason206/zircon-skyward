#!/usr/bin/env bash
set -euo pipefail
SKYWARD_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
export SKYWARD_ROOT
source "$SKYWARD_ROOT/scripts/env.sh"
cd "$SKYWARD_ROOT"
skyward_stock="$SKYWARD_ROOT/target/stock/zircon/vendor_boot.img"
skyward_boot="$SKYWARD_ROOT/target/stock/zircon/boot.img"
skyward_out="$SKYWARD_ROOT/out/zircon"
skyward_skip_build=false
while [ "$#" -gt 0 ]; do
    case "$1" in
        --stock|--boot|--out)
            if [ "$#" -lt 2 ]; then printf 'Missing value for %s\n' "$1" >&2; exit 2; fi
            case "$1" in
                --stock) skyward_stock="$2" ;;
                --boot) skyward_boot="$2" ;;
                --out) skyward_out="$2" ;;
            esac
            shift 2 ;;
        --skip-build) skyward_skip_build=true; shift ;;
        --help)
            printf '%s\n' 'Usage: scripts/build-zircon.sh [--stock vendor_boot.img] [--boot boot.img] [--out directory] [--skip-build]'
            exit 0 ;;
        *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
    esac
done
test -f "$skyward_stock" || { printf 'Missing stock image: %s\nUse --stock /path/to/vendor_boot.img\n' "$skyward_stock" >&2; exit 1; }
test -f "$skyward_boot" || { printf 'Missing paired stock boot image: %s\nUse --boot /path/to/boot.img\n' "$skyward_boot" >&2; exit 1; }
"$SKYWARD_PYTHON" scripts/verify-zircon.py --stock "$skyward_stock" --boot "$skyward_boot"

if [ "$skyward_skip_build" = false ]; then
    cargo build --locked --release -p skyward-pack
    cargo ndk -t arm64-v8a --platform "$SKYWARD_API" build --locked --release -p skyward
    RUSTFLAGS="-C target-feature=+crt-static" cargo ndk -t arm64-v8a --platform "$SKYWARD_API" \
        build --locked --release -p skyward-system-init --target-dir target/system-init
fi
skyward_name=$("$SKYWARD_PYTHON" - <<'PY'
import re, tomllib
from pathlib import Path
workspace = tomllib.loads(Path('Cargo.toml').read_text())
device = tomllib.loads(Path('devices/zircon.toml').read_text())
version, stock = workspace['workspace']['package']['version'], device['stock']['version']
assert all(re.fullmatch(r'[A-Za-z0-9._-]+', value) for value in (version, stock))
print(f'skyward-v{version}-zircon-{stock}-experimental')
PY
)
mkdir -p "$skyward_out"
skyward_image="$skyward_out/$skyward_name.img"
skyward_binary="$SKYWARD_ROOT/target/aarch64-linux-android/release/skyward"
skyward_system_init="$SKYWARD_ROOT/target/system-init/aarch64-linux-android/release/system-init"
target/release/skyward-pack recovery \
    --stock "$skyward_stock" --binary "$skyward_binary" --system-init "$skyward_system_init" \
    --config devices/zircon.toml --font resources/fonts/MiSansVF.ttf \
    --mono resources/fonts/KirkMono-Regular.ttf --mono-license resources/fonts/KirkMono-OFL.txt \
    --add /skyward/avatar.png=resources/avatar.png --out "$skyward_image"
"$SKYWARD_PYTHON" scripts/verify-zircon.py --stock "$skyward_stock" --boot "$skyward_boot" \
    --image "$skyward_image" --binary "$skyward_binary" --system-init "$skyward_system_init" \
    --report "$skyward_out/verification.json"
"$SKYWARD_PYTHON" - "$skyward_image" "$SKYWARD_ROOT" <<'PY'
import hashlib, json, os, platform, subprocess, sys, tomllib, zipfile
from pathlib import Path
image, root = map(Path, sys.argv[1:])
archive = image.with_suffix('.zip')
workspace = tomllib.loads((root / 'Cargo.toml').read_text())
config = tomllib.loads((root / 'devices/zircon.toml').read_text())
report = json.loads((image.parent / 'verification.json').read_text())
version = workspace['workspace']['package']['version']
repository = 'https://github.com/' + config['skyward']['releases']

def command(*args):
    result = subprocess.run(args, cwd=root, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None

git_root = command('git', 'rev-parse', '--show-toplevel')
in_checkout = bool(git_root and Path(git_root).resolve() == root.resolve())
revision = command('git', 'rev-parse', 'HEAD') if in_checkout else None
dirty = bool(command('git', 'status', '--porcelain')) if in_checkout else None
epoch = os.environ.get('SOURCE_DATE_EPOCH') or (command('git', 'show', '-s', '--format=%ct', 'HEAD') if in_checkout else None)
ndk_properties = Path(os.environ['ANDROID_NDK_HOME'], 'source.properties').read_text()
ndk_version = next(line.split('=', 1)[1].strip() for line in ndk_properties.splitlines() if line.startswith('Pkg.Revision'))
buildinfo = {
    'version': version,
    'source_repository': repository,
    'source_tag': f'v{version}',
    'source_commit': revision,
    'source_worktree_dirty': dirty,
    'source_date_epoch': int(epoch) if epoch else None,
    'build_host': {'os': platform.system(), 'architecture': platform.machine()},
    'rust': command('rustc', '--version'),
    'cargo_ndk': command('cargo', 'ndk', '--version'),
    'android_ndk': ndk_version,
    'android_api': int(os.environ['SKYWARD_API']),
    'stock_version': report['stock_version'],
    'stock_boot_sha256': report['stock_boot_sha256'],
    'stock_vendor_boot_sha256': report['stock_vendor_boot_sha256'],
    'image': image.name,
    'image_sha256': report['image_sha256'],
    'image_size': report['image_size'],
    'binaries': report['binaries'],
    'offline_verification': report['result'],
    'phone_tested': False,
}
(image.parent / 'BUILDINFO.json').write_text(json.dumps(buildinfo, ensure_ascii=False, indent=2) + '\n')
source = (f'Skyward for zircon v{version}\nSource / 源码: {repository}/tree/v{version}\n'
          f'Commit / 提交: {revision or "source archive; commit unknown"}\n'
          'License / 许可: GPL-3.0-or-later; see LICENSE and NOTICE.md.\n')
(image.parent / 'SOURCE.txt').write_text(source)
readme = (f'Skyward for zircon v{version} — experimental alpha / 实验版\n'
          'Stock / 原厂版本: OS3.0.305.0.WNOCNXM\n'
          'Target / 目标分区: vendor_boot\n'
          'Built and verified offline; not boot-tested on a phone.\n'
          '已编译并通过离线校验，尚未进行实机启动。\n'
          'Wi-Fi, haptics, FBE decryption and dual boot need device validation.\n'
          'Wi-Fi、震动、FBE 解密及双系统仍需实机验证。\n'
          f'Documentation / 说明: {repository}\n')
files = [(image.name, image.read_bytes()), ('README.txt', readme.encode('utf-8'))]
for name in ('README.md', 'README.zh-CN.md', 'LICENSE', 'NOTICE.md', 'docs/ZIRCON.md',
             'docs/ZIRCON.zh-CN.md', 'devices/zircon.toml', 'devices/zircon-stock.json',
             'resources/fonts/KirkMono-OFL.txt'):
    files.append((name, (root / name).read_bytes()))
for name in ('verification.json', 'BUILDINFO.json', 'SOURCE.txt'):
    files.append((name, (image.parent / name).read_bytes()))
with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
    for name, content in files:
        info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        output.writestr(info, content, compresslevel=9)
with zipfile.ZipFile(archive) as output:
    assert output.testzip() is None
    assert hashlib.sha256(output.read(image.name)).digest() == hashlib.sha256(image.read_bytes()).digest()
assets = (image, archive, image.parent / 'verification.json', image.parent / 'BUILDINFO.json', image.parent / 'SOURCE.txt')
checksums = ''.join(f'{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n' for path in assets)
(image.parent / 'SHA256SUMS').write_text(checksums)
print(f'Built and verified: {image}\nArchive: {archive}')
PY
