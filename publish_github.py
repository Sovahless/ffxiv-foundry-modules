#!/usr/bin/env python3
"""
FFXIV Foundry VTT Modules — Single-Repo Publisher (Sovahless/ffxiv-foundry-modules)

Maintains per-module manifests under manifests/<id>/module.json on branch `main`
and uploads clean runtime .zip archives as independent GitHub Releases:
  Tag: <id>-v<version>   Asset: <id>.zip
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

GITHUB_OWNER = "Sovahless"
REPO_NAME = "ffxiv-foundry-modules"
REPO_SLUG = f"{GITHUB_OWNER}/{REPO_NAME}"
REPO_URL = f"https://github.com/{REPO_SLUG}"

REPO_ROOT = Path(__file__).resolve().parent
MANIFESTS_DIR = REPO_ROOT / "manifests"
DIST_DIR = REPO_ROOT / "dist"
MODULES_DATA_DIR = Path(r"C:\Users\Sovahless\AppData\Local\FoundryVTT\Data\modules")

MODULE_INCLUDES: dict[str, list[str]] = {
    "ffxiv-dnd5e-dawntrail": ["module.json", "assets", "lang", "packs_v3", "scripts", "styles"],
    "ffxiv-dnd5e-limit-break": ["module.json", "lang", "scripts", "styles", "templates"],
    "ffxiv-dnd5e-raimdelle-bestiary": ["module.json", "assets", "lang", "packs"],
    "ffxiv-dnd5e-materia": ["module.json", "assets", "lang", "packs", "scripts", "styles"],
}

OPTIONAL_MODULES: dict[str, list[str]] = {
    "ffxiv-dnd5e-ultimates": ["module.json", "assets", "lang", "packs", "scripts", "styles", "templates"],
}

SKIP_FILENAMES = {"LOCK", "LOG", "LOG.old", ".DS_Store", "Thumbs.db"}


def resolve_gh_bin() -> str:
    found = shutil.which("gh")
    if found:
        return found
    candidate = Path(r"C:\Program Files\GitHub CLI\gh.exe")
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("GitHub CLI (gh) introuvable.")


def bump_semver(version: str, part: str) -> str:
    pieces = [int(x) for x in version.strip().split(".")]
    while len(pieces) < 3:
        pieces.append(0)
    if part == "major":
        return f"{pieces[0] + 1}.0.0"
    if part == "minor":
        return f"{pieces[0]}.{pieces[1] + 1}.0"
    if part == "patch":
        return f"{pieces[0]}.{pieces[1]}.{pieces[2] + 1}"
    raise ValueError(f"Unsupported bump kind: {part}")


def build_urls(mod_id: str, version: str) -> tuple[str, str, str]:
    manifest_url = (
        f"https://raw.githubusercontent.com/{REPO_SLUG}/main/manifests/{mod_id}/module.json"
    )
    download_url = (
        f"https://github.com/{REPO_SLUG}/releases/download/{mod_id}-v{version}/{mod_id}.zip"
    )
    return REPO_URL, manifest_url, download_url


def sync_manifest(mod_id: str, bump: str | None) -> dict[str, Any]:
    src_dir = MODULES_DATA_DIR / mod_id
    manifest_path = src_dir / "module.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {manifest_path}")

    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(data["version"])
    if bump:
        version = bump_semver(version, bump)
        data["version"] = version

    url, manifest_url, download_url = build_urls(mod_id, version)
    data["url"] = url
    data["manifest"] = manifest_url
    data["download"] = download_url

    serialized = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    manifest_path.write_text(serialized, encoding="utf-8", newline="\n")

    repo_manifest_path = MANIFESTS_DIR / mod_id / "module.json"
    repo_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    repo_manifest_path.write_text(serialized, encoding="utf-8", newline="\n")
    return data


def package_module_zip(mod_id: str, includes: list[str], manifest_data: dict[str, Any]) -> Path:
    src_dir = MODULES_DATA_DIR / mod_id
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    zip_path = DIST_DIR / f"{mod_id}.zip"
    if zip_path.exists():
        zip_path.unlink()

    file_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for entry_name in includes:
            target = src_dir / entry_name
            if not target.exists():
                raise FileNotFoundError(f"Configured include {entry_name} missing in {src_dir}")
            if target.is_file():
                arc = (PurePosixPath(mod_id) / PurePosixPath(entry_name)).as_posix()
                zf.write(target, arcname=arc)
                file_count += 1
            else:
                for root, _, files in os.walk(target):
                    root_p = Path(root)
                    for fname in sorted(files):
                        if fname in SKIP_FILENAMES:
                            continue
                        full_p = root_p / fname
                        rel_p = full_p.relative_to(src_dir)
                        arc = (PurePosixPath(mod_id) / PurePosixPath(*rel_p.parts)).as_posix()
                        zf.write(full_p, arcname=arc)
                        file_count += 1

    verify_zip_archive(zip_path, mod_id, manifest_data, file_count)
    return zip_path


def verify_zip_archive(
    zip_path: Path, mod_id: str, expected_manifest: dict[str, Any], expected_count: int
) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = zf.infolist()
        if len(infos) != expected_count:
            raise AssertionError(f"{zip_path.name}: expected {expected_count} files, got {len(infos)}")

        names = set()
        for info in infos:
            if "\\" in info.filename:
                raise AssertionError(f"{zip_path.name}: backslash in zip entry {info.filename}")
            base = PurePosixPath(info.filename).name
            if base in SKIP_FILENAMES:
                raise AssertionError(f"{zip_path.name}: disallowed file {info.filename}")
            if base == "CURRENT" and ("/packs/" in info.filename or "/packs_v3/" in info.filename):
                raw = zf.read(info.filename)
                if raw.endswith(b"\r\n") or not raw.endswith(b"\n"):
                    raise AssertionError(f"{zip_path.name}: invalid LevelDB CURRENT LF in {info.filename}")
            names.add(info.filename)

        mj_arc = f"{mod_id}/module.json"
        if mj_arc not in names:
            raise AssertionError(f"{zip_path.name}: missing {mj_arc}")
        packed_mj = json.loads(zf.read(mj_arc).decode("utf-8"))
        for key in ("id", "version", "manifest", "download"):
            if packed_mj.get(key) != expected_manifest.get(key):
                raise AssertionError(
                    f"{zip_path.name}: mismatch on {key}: {packed_mj.get(key)} != {expected_manifest.get(key)}"
                )

    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  OK {zip_path.name}: {expected_count} files ({size_mb:.2f} MB) [verified]")


def write_readme(manifests: dict[str, dict[str, Any]]) -> None:
    rows = []
    for mod_id, mj in manifests.items():
        rows.append(
            f"| `{mod_id}` | `{mj['version']}` | `{mj['manifest']}` |"
        )
    table = "\n".join(rows)

    readme = f"""# FFXIV Foundry VTT Modules (`{REPO_SLUG}`)

Dépôt central pour installer et mettre à jour indépendamment les modules **FFXIV x D&D 5e** sur Foundry VTT v14 (`dnd5e` v6.1.1).

Chaque module possède son propre `manifest` dans `manifests/<id>/module.json` et sa propre Release GitHub (`<id>-v<version>`) : mettre à jour un module ne force pas le retéléchargement des autres.

## Liens d'installation Foundry VTT (Manifest URL)

Dans **Modules complémentaires → Installer un module → URL du manifeste** :

| Module | Version | URL du manifeste |
|---|---|---|
{table}

## Publier une mise à jour depuis Windows

```powershell
# Mettre à jour un module précis (incrémente la version patch + push + GitHub Release)
python publish_github.py --module ffxiv-dnd5e-materia --bump patch --publish

# Ou re-publier tous les modules sans changer les versions
python publish_github.py --publish
```
"""
    (REPO_ROOT / "README.md").write_text(readme, encoding="utf-8", newline="\n")


def run_cmd(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    print(" >", " ".join(cmd))
    return subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True, check=check)


def ensure_github_repo(gh_bin: str) -> None:
    rem = run_cmd(["git", "remote", "get-url", "origin"], check=False)
    if rem.returncode != 0:
        view = run_cmd([gh_bin, "repo", "view", REPO_SLUG], check=False)
        if view.returncode == 0:
            run_cmd(["git", "remote", "add", "origin", f"https://github.com/{REPO_SLUG}.git"])
        else:
            res = run_cmd(
                [gh_bin, "repo", "create", REPO_SLUG, "--public", "--source=.", "--remote=origin"],
                check=False,
            )
            if res.returncode != 0:
                raise RuntimeError(f"gh repo create failed:\n{res.stdout}\n{res.stderr}")


def git_commit_and_push(commit_msg: str) -> None:
    run_cmd(["git", "add", "README.md", ".gitignore", ".gitattributes", "publish_github.py", "publish.ps1", "manifests"])
    status = run_cmd(["git", "status", "--porcelain"])
    if status.stdout.strip():
        run_cmd(["git", "commit", "-m", commit_msg])
    res = run_cmd(["git", "push", "-u", "origin", "main"], check=False)
    if res.returncode != 0:
        raise RuntimeError(f"git push failed:\n{res.stdout}\n{res.stderr}")


def publish_release(gh_bin: str, mod_id: str, manifest_data: dict[str, Any], zip_path: Path) -> None:
    version = manifest_data["version"]
    tag = f"{mod_id}-v{version}"
    title = f"{manifest_data.get('title', mod_id)} v{version}"
    notes = (
        f"Release `{mod_id}` v{version} (Foundry VTT v14 / dnd5e v6.1.1).\n\n"
        f"**Manifest URL:** `{manifest_data['manifest']}`"
    )

    view = run_cmd([gh_bin, "release", "view", tag, "--repo", REPO_SLUG], check=False)
    if view.returncode == 0:
        res = run_cmd(
            [gh_bin, "release", "upload", tag, str(zip_path), "--repo", REPO_SLUG, "--clobber"],
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"gh release upload failed for {tag}:\n{res.stderr}")
        print(f"  Updated release asset on {tag}")
    else:
        res = run_cmd(
            [
                gh_bin,
                "release",
                "create",
                tag,
                str(zip_path),
                "--repo",
                REPO_SLUG,
                "--target",
                "main",
                "--title",
                title,
                "--notes",
                notes,
            ],
            check=False,
        )
        if res.returncode != 0:
            raise RuntimeError(f"gh release create failed for {tag}:\n{res.stderr}")
        print(f"  Created release {tag}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish FFXIV Foundry modules to GitHub.")
    parser.add_argument("--module", action="append", help="Specific module ID(s) to process.")
    parser.add_argument("--bump", choices=["patch", "minor", "major"], help="Increment module version.")
    parser.add_argument("--include-ultimates", action="store_true", help="Also include ffxiv-dnd5e-ultimates.")
    parser.add_argument("--prepare-only", action="store_true", help="Build manifests and zips without pushing.")
    parser.add_argument("--publish", action="store_true", help="Commit, push, and publish GitHub releases.")
    args = parser.parse_args()

    catalog = dict(MODULE_INCLUDES)
    if args.include_ultimates:
        catalog.update(OPTIONAL_MODULES)

    selected_ids = args.module if args.module else list(catalog.keys())
    for mid in selected_ids:
        if mid not in catalog:
            if mid in OPTIONAL_MODULES:
                catalog[mid] = OPTIONAL_MODULES[mid]
            else:
                print(f"Error: Unknown module '{mid}'", file=sys.stderr)
                return 1

    print("=== Syncing manifests & building archives ===")
    all_manifests: dict[str, dict[str, Any]] = {}
    built_zips: dict[str, Path] = {}

    for mid in catalog:
        bump = args.bump if mid in selected_ids else None
        mj = sync_manifest(mid, bump)
        all_manifests[mid] = mj
        if mid in selected_ids:
            built_zips[mid] = package_module_zip(mid, catalog[mid], mj)

    write_readme(all_manifests)

    if args.prepare_only or not args.publish:
        print("=== Prepare-only complete (not pushed) ===")
        return 0

    gh_bin = resolve_gh_bin()
    auth = run_cmd([gh_bin, "auth", "status"], check=False)
    if auth.returncode != 0:
        print("Error: GitHub CLI not authenticated. Run: gh auth login", file=sys.stderr)
        return 1

    ensure_github_repo(gh_bin)
    commit_label = ", ".join(f"{mid}@{all_manifests[mid]['version']}" for mid in selected_ids)
    git_commit_and_push(f"Release {commit_label}")

    print("=== Publishing GitHub Releases ===")
    for mid in selected_ids:
        publish_release(gh_bin, mid, all_manifests[mid], built_zips[mid])

    print("=== Done ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
