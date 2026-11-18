#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
python_bin="${PYTHON:-python}"

npm --prefix frontend ci
npm --prefix frontend run build

"$python_bin" -m PyInstaller --noconfirm --onedir \
    --name zfundpilot-backend --paths src \
    --distpath desktop/build/backend --workpath desktop/build/work \
    --specpath desktop/build --add-data "$PWD/frontend/dist:frontend/dist" \
    --collect-data akshare --collect-all py_mini_racer \
    --hidden-import uvicorn.loops.asyncio --hidden-import uvicorn.lifespan.on \
    src/zfundpilot/desktop_backend.py

cd desktop
npm ci
# 构建工具本身也以 AppImage 分发，允许在没有 FUSE 的 CI 和容器中运行。
APPIMAGE_EXTRACT_AND_RUN=1 npm exec -- tauri build --target x86_64-unknown-linux-gnu -- --locked

bundle="$PWD/src-tauri/target/x86_64-unknown-linux-gnu/release/bundle"
shopt -s nullglob
version=$(node -p "require('../frontend/package.json').version")
deb=("$bundle"/deb/*_"${version}"_amd64.deb)
appimage=("$bundle"/appimage/*_"${version}"_amd64.AppImage)
if (( ${#deb[@]} != 1 || ${#appimage[@]} != 1 )); then
    echo "预期生成一个 deb 和一个 AppImage，请检查输出目录 $bundle" >&2
    exit 1
fi

# 在最终包的资源目录启动后端，检查执行权限、动态库与前端资源。
temporary=$(mktemp -d)
trap 'rm -rf -- "$temporary"' EXIT
dpkg-deb -x "${deb[0]}" "$temporary/deb"
(cd "$temporary" && "${appimage[0]}" --appimage-extract > /dev/null)
for extracted in "$temporary/deb" "$temporary/squashfs-root"; do
    "$python_bin" smoke_backend.py "$extracted/usr/lib/ZFundPilot/backend/zfundpilot-backend"
done
