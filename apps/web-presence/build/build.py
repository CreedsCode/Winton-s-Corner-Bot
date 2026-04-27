#!/usr/bin/env python3
import hashlib, re
from pathlib import Path
import rjsmin, rcssmin
import shutil

SRC = Path("src")
OUT = Path("public")
OUT.mkdir(parents=True, exist_ok=True)

def hash_bytes(b): return hashlib.sha256(b).hexdigest()[:8]

def minify_file(path: Path):
    txt = path.read_text(encoding='utf8')
    if path.suffix == '.js':
        return rjsmin.jsmin(txt).encode('utf8')
    if path.suffix == '.css':
        return rcssmin.cssmin(txt).encode('utf8')
    if path.suffix == '.html':
        return txt.encode('utf8')
    return txt.encode('utf8')


files = [p for p in SRC.rglob('*') if p.is_file() and p.suffix in ('.js', '.css', '.html')]
manifest = {}
buffer = {}

for p in files:
    rel = p.relative_to(SRC)
    rel_posix = rel.as_posix()
    if p.suffix in ('.js', '.css'):
        b = minify_file(p)
        name = p.stem
        h = hash_bytes(b)
        out_filename = f"{name}.{h}{p.suffix}"

        out_subdir = OUT / rel.parent
        out_subdir.mkdir(parents=True, exist_ok=True)
        out_path = out_subdir / out_filename
        out_path.write_bytes(b)

        manifest[rel_posix] = (rel.parent / out_filename).as_posix()
        buffer[rel_posix] = b

def replace_refs(html_text, manifest_map):
    def repl(m):
        orig = m.group(1)

        if orig in manifest_map:
            return m.group(0).replace(orig, manifest_map[orig])

        bname = Path(orig).name

        orig_parent = Path(orig).parent.name
        for k, v in manifest_map.items():
            if Path(k).name == bname:
                return m.group(0).replace(orig, '/' + v)
        return m.group(0)

    return re.sub(r'(?:src|href)=["\']([^"\']+)["\']', repl, html_text)

for p in files:
    if p.suffix == '.html':
        raw = p.read_text(encoding='utf8')
        replaced = replace_refs(raw, manifest)
        b = replaced.encode('utf8')

        out_subdir = OUT / p.relative_to(SRC).parent
        out_subdir.mkdir(parents=True, exist_ok=True)
        out_path = out_subdir / p.name
        out_path.write_bytes(b)

        rel_posix = p.relative_to(SRC).as_posix()
        manifest[rel_posix] = (p.relative_to(SRC).parent / p.name).as_posix()
        buffer[rel_posix] = b

for p in SRC.rglob('*'):
    if not p.is_file():
        continue
    if p.suffix in ('.js', '.css', '.html'):
        continue
    out_path = OUT / p.relative_to(SRC)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, out_path)