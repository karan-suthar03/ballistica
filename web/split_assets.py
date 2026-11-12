#!/usr/bin/env python3
"""Merge per-texture-profile asset caches and split them for the web.

Web builds have no plus, so they can't download asset packages; they
ship caches a native build downloaded (one per texture profile, see
web/fetch_flavors.sh). Shipping all profiles in one .data would make
every browser download every texture set, so this splits them:

  <out>/base/            manifest.json (all profiles' flavors merged)
                         + every blob that isn't one profile's texture
  <out>/tex-<profile>/   blobs used only by that profile's textures

The shell loads base plus the one texture package matching the GPU,
picked the same way as Assets::PreferredTextureProfile on web. Flavors
whose blobs are missing are simply not complete locally, so they're
never chosen.

usage: split_assets.py <out> <profile>=<cache-dir> [...]
"""

import json
import os
import shutil
import sys
from pathlib import Path


def blob(cache: Path, h: str) -> Path:
    return cache / 'assets' / h[:2] / h[2:]


# Bundled blobs (ba_data/assets) already ship in base; flavor manifests
# for builtin flavors may live only there.
BUNDLE = Path(os.environ.get('BA_BUNDLE', 'build/cmake/debug/staged/ba_data'))


def texture_blobs(cache: Path, fm_hash: str) -> set[str]:
    path = blob(cache, fm_hash)
    if not path.exists():
        path = blob(BUNDLE, fm_hash)
    entries = json.loads(path.read_bytes())['e']
    return {c['h'] for info in entries.values() for c in info.values()}


def main() -> None:
    out = Path(sys.argv[1])
    caches = {
        k: Path(v) for k, v in (a.split('=', 1) for a in sys.argv[2:])
    }
    merged: dict = {'v': None, 'p': {}, 'f': {}}
    tex: dict[str, set[str]] = {p: set() for p in caches}
    where: dict[str, Path] = {}
    for profile, cache in caches.items():
        man = json.loads((cache / 'manifest.json').read_text())
        merged['v'] = merged['v'] or man['v']
        merged['f'].update(man['f'])
        for apv, pkg in man['p'].items():
            dst = merged['p'].setdefault(apv, {'fm': {}, 'lu': pkg['lu']})
            dst['fm'].update(pkg['fm'])
            for coord, fm_hash in pkg['fm'].items():
                if coord.startswith(f'textures/{profile}.'):
                    tex[profile] |= texture_blobs(cache, fm_hash)
        for d in (cache / 'assets').iterdir():
            for f in d.iterdir():
                where.setdefault(d.name + f.name, f)

    # A blob shared by several profiles goes in base.
    owner: dict[str, str] = {}
    for profile, hashes in tex.items():
        for h in hashes:
            owner[h] = 'base' if h in owner else profile

    if out.exists():
        shutil.rmtree(out)
    (out / 'base').mkdir(parents=True)
    (out / 'base' / 'manifest.json').write_text(json.dumps(merged))
    sizes: dict[str, int] = {}
    for h, src in where.items():
        pack = owner.get(h, 'base')
        name = 'base' if pack == 'base' else f'tex-{pack}'
        dst = out / name / 'assets' / h[:2] / h[2:]
        dst.parent.mkdir(parents=True, exist_ok=True)
        os.link(src, dst)
        sizes[name] = sizes.get(name, 0) + src.stat().st_size
    for name, size in sorted(sizes.items()):
        print(f'{name}: {size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
