#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import zipfile

from github_utils import github_request


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_DEST = PROJECT_ROOT / ".agents" / "skills"
DEFAULT_REF = "main"
KNOWN_LOCALIZED_NAMES = {
    "skill-creator": "创建技能",
    "skill-installer": "安装技能",
}
NOISE_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}


@dataclass
class Args:
    url: str | None = None
    repo: str | None = None
    path: list[str] | None = None
    ref: str = DEFAULT_REF
    dest: str | None = None
    name: str | None = None
    method: str = "auto"


@dataclass
class Source:
    owner: str
    repo: str
    ref: str
    paths: list[str]
    repo_url: str | None = None


class InstallError(Exception):
    pass


def request(url: str) -> bytes:
    return github_request(url, "zqz-orchestrator-skill-install")


def temp_root() -> str:
    base = os.path.join(tempfile.gettempdir(), "zqz_orchestrator_skill_install")
    os.makedirs(base, exist_ok=True)
    return base


def parse_github_url(url: str, default_ref: str) -> tuple[str, str, str, str | None]:
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != "github.com":
        raise InstallError("当前安装脚本只支持 GitHub URL。")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise InstallError("GitHub URL 不完整。")
    owner, repo = parts[0], parts[1]
    ref = default_ref
    subpath = ""
    if len(parts) > 2:
        if parts[2] in ("tree", "blob"):
            if len(parts) < 4:
                raise InstallError("GitHub URL 缺少 ref 或路径。")
            ref = parts[3]
            subpath = "/".join(parts[4:])
        else:
            subpath = "/".join(parts[2:])
    return owner, repo, ref, subpath or None


def safe_extract_zip(zip_file: zipfile.ZipFile, dest_dir: str) -> None:
    dest_root = os.path.realpath(dest_dir)
    for info in zip_file.infolist():
        extracted = os.path.realpath(os.path.join(dest_dir, info.filename))
        if extracted == dest_root or extracted.startswith(dest_root + os.sep):
            continue
        raise InstallError("压缩包包含越界路径。")
    zip_file.extractall(dest_dir)


def download_repo_zip(owner: str, repo: str, ref: str, dest_dir: str) -> str:
    url = f"https://codeload.github.com/{owner}/{repo}/zip/{ref}"
    zip_path = os.path.join(dest_dir, "repo.zip")
    try:
        payload = request(url)
    except urllib.error.HTTPError as exc:
        raise InstallError(f"下载仓库失败：HTTP {exc.code}") from exc
    with open(zip_path, "wb") as handle:
        handle.write(payload)
    with zipfile.ZipFile(zip_path, "r") as archive:
        safe_extract_zip(archive, dest_dir)
        top_levels = {name.split("/")[0] for name in archive.namelist() if name}
    if len(top_levels) != 1:
        raise InstallError("下载后的仓库结构异常。")
    return os.path.join(dest_dir, next(iter(top_levels)))


def run_git(args: list[str]) -> None:
    result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise InstallError(result.stderr.strip() or "Git 命令执行失败。")


def git_sparse_checkout(repo_url: str, ref: str, paths: list[str], dest_dir: str) -> str:
    repo_dir = os.path.join(dest_dir, "repo")
    clone_cmd = [
        "git",
        "clone",
        "--filter=blob:none",
        "--depth",
        "1",
        "--sparse",
        "--single-branch",
        "--branch",
        ref,
        repo_url,
        repo_dir,
    ]
    try:
        run_git(clone_cmd)
    except InstallError:
        run_git(
            [
                "git",
                "clone",
                "--filter=blob:none",
                "--depth",
                "1",
                "--sparse",
                "--single-branch",
                repo_url,
                repo_dir,
            ]
        )
    run_git(["git", "-C", repo_dir, "sparse-checkout", "set", *paths])
    run_git(["git", "-C", repo_dir, "checkout", ref])
    return repo_dir


def build_repo_url(owner: str, repo: str) -> str:
    return f"https://github.com/{owner}/{repo}.git"


def build_repo_ssh(owner: str, repo: str) -> str:
    return f"git@github.com:{owner}/{repo}.git"


def prepare_repo(source: Source, method: str, tmp_dir: str) -> str:
    if method in ("download", "auto"):
        try:
            return download_repo_zip(source.owner, source.repo, source.ref, tmp_dir)
        except InstallError as exc:
            if method == "download":
                raise
            message = str(exc)
            if "HTTP 401" not in message and "HTTP 403" not in message and "HTTP 404" not in message:
                raise
    if method in ("git", "auto"):
        try:
            return git_sparse_checkout(
                source.repo_url or build_repo_url(source.owner, source.repo),
                source.ref,
                source.paths,
                tmp_dir,
            )
        except InstallError:
            return git_sparse_checkout(build_repo_ssh(source.owner, source.repo), source.ref, source.paths, tmp_dir)
    raise InstallError("不支持的安装方式。")


def validate_relative_path(path: str) -> None:
    if os.path.isabs(path) or os.path.normpath(path).startswith(".."):
        raise InstallError("skill 路径必须是仓库内的相对路径。")


def validate_skill_dir(path: Path) -> None:
    if not path.is_dir():
        raise InstallError(f"找不到 skill 目录：{path}")
    if not (path / "SKILL.md").is_file():
        raise InstallError(f"目标目录不是有效 skill：{path}")


def extract_frontmatter(text: str) -> str | None:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    return match.group(1)


def frontmatter_value(frontmatter: str | None, key: str) -> str | None:
    if not frontmatter:
        return None
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def read_source_metadata(skill_dir: Path) -> tuple[str, str]:
    text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = extract_frontmatter(text)
    source_name = frontmatter_value(frontmatter, "name") or skill_dir.name
    source_description = frontmatter_value(frontmatter, "description") or f"与 {source_name} 相关的外部 skill。"
    return source_name, source_description


def contains_chinese(text: str | None) -> bool:
    return bool(text and re.search(r"[\u4e00-\u9fff]", text))


def sanitize_skill_name(name: str) -> str:
    sanitized = re.sub(r'[\\/:*?"<>|]+', "", name).strip()
    sanitized = re.sub(r"\s+", " ", sanitized)
    if not sanitized:
        raise InstallError("本地 skill 名无效。")
    if sanitized in {".", ".."}:
        raise InstallError("本地 skill 名无效。")
    return sanitized


def suggest_local_name(source_name: str, fallback_name: str, override: str | None) -> str:
    if override:
        return sanitize_skill_name(override)
    for candidate in (source_name, fallback_name):
        if contains_chinese(candidate):
            return sanitize_skill_name(candidate)
    normalized = fallback_name.strip().lower()
    if normalized in KNOWN_LOCALIZED_NAMES:
        return KNOWN_LOCALIZED_NAMES[normalized]
    return sanitize_skill_name(f"{fallback_name}迁入技能")


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    counter = 2
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def ensure_standard_dirs(skill_root: Path) -> None:
    for dirname in ("agents", "references", "scripts", "assets"):
        (skill_root / dirname).mkdir(parents=True, exist_ok=True)


def write_openai_yaml(skill_root: Path, display_name: str) -> None:
    short_description = f"用于{display_name}相关任务"
    content = "\n".join(
        [
            "interface:",
            f'  display_name: "{display_name}"',
            f'  short_description: "{short_description[:64]}"',
            "",
        ]
    )
    (skill_root / "agents" / "openai.yaml").write_text(content, encoding="utf-8")


def thin_skill_markdown(local_name: str, source_name: str, source_description: str) -> str:
    return f"""---
name: {local_name}
description: 当用户需要与“{source_name}”相关的能力，或要在当前项目里复用该外部 skill 的工作流时使用。当前入口已被本地化为中文薄 skill，原始长说明请按需展开 references。
---

# {local_name}

## 这项技能解决什么问题

- 复用来源 skill “{source_name}” 的核心能力
- 以当前项目可维护的中文薄入口方式承接原始长说明
- 避免把原始厚 `SKILL.md` 直接留在热路径

## 先读哪些本地知识

- 如果这项 skill 依赖工作区业务真相，先读对应工作区 `knowledge/`
- 需要回看原始说明时，再读 `references/原始技能说明.md`
- 需要了解这次迁入时的本地化取舍时，再读 `references/迁移说明.md`

## 固定动作

1. 先确认当前任务是否真的需要“{source_name}”这类能力
2. 默认先看本地薄入口和已有 `scripts/`、`assets/`
3. 遇到复杂分支或边界判断，再展开 `references/原始技能说明.md`
4. 如果发现原始规则与当前项目冲突，继续本地收口，不把长说明搬回 `SKILL.md`

## 什么时候再读本 skill 的 references

- 需要完整原始用法、原始边界或原始示例时，再读 `references/原始技能说明.md`
- 需要确认本次迁移来源、原始描述和本地化动作时，再读 `references/迁移说明.md`

## 边界

- 不把原始长说明重新塞回 `SKILL.md`
- 不保留根目录噪音文档作为热路径入口
- 不跳过当前项目已有的本地边界与治理约束
"""


def migration_note(source: Source, source_path: str, source_name: str, source_description: str) -> str:
    return f"""# 迁移说明

- 来源仓库：`{source.owner}/{source.repo}`
- 来源 ref：`{source.ref}`
- 来源路径：`{source_path}`
- 原始名称：`{source_name}`
- 原始描述：{source_description}

本地化动作：

1. 保留原始 `SKILL.md` 到 `references/原始技能说明.md`
2. 重新生成中文薄 `SKILL.md`
3. 重新生成中文 `agents/openai.yaml`
4. 补齐 `agents/`、`references/`、`scripts/`、`assets/`
5. 清理根目录 README / CHANGELOG 等噪音文件
"""


def move_original_entry(skill_root: Path, relative_path: str, target_name: str) -> None:
    source_path = skill_root / relative_path
    if not source_path.exists():
        return
    target_path = unique_path(skill_root / "references" / target_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(target_path))


def cleanup_root_noise(skill_root: Path) -> None:
    for filename in NOISE_ROOT_FILES:
        candidate = skill_root / filename
        if candidate.exists():
            candidate.unlink()


def copy_skill_tree(source_dir: Path, dest_dir: Path) -> None:
    if dest_dir.exists():
        raise InstallError(f"目标 skill 已存在：{dest_dir}")
    ignore = shutil.ignore_patterns("__pycache__", ".git", ".DS_Store")
    shutil.copytree(source_dir, dest_dir, ignore=ignore)


def localize_installed_skill(source: Source, source_path: str, source_dir: Path, dest_root: Path, requested_name: str | None) -> Path:
    source_name, source_description = read_source_metadata(source_dir)
    local_name = suggest_local_name(source_name, source_dir.name, requested_name)
    dest_dir = dest_root / local_name
    copy_skill_tree(source_dir, dest_dir)
    ensure_standard_dirs(dest_dir)
    move_original_entry(dest_dir, "SKILL.md", "原始技能说明.md")
    move_original_entry(dest_dir, os.path.join("agents", "openai.yaml"), "原始openai.yaml")
    cleanup_root_noise(dest_dir)
    (dest_dir / "SKILL.md").write_text(
        thin_skill_markdown(local_name, source_name, source_description),
        encoding="utf-8",
    )
    (dest_dir / "references" / "迁移说明.md").write_text(
        migration_note(source, source_path, source_name, source_description),
        encoding="utf-8",
    )
    write_openai_yaml(dest_dir, local_name)
    if not any((dest_dir / "scripts").iterdir()):
        (dest_dir / "scripts" / ".gitkeep").write_text("", encoding="utf-8")
    if not any((dest_dir / "assets").iterdir()):
        (dest_dir / "assets" / ".gitkeep").write_text("", encoding="utf-8")
    return dest_dir


def resolve_source(args: Args) -> Source:
    if args.url:
        owner, repo, ref, url_path = parse_github_url(args.url, args.ref)
        paths = list(args.path) if args.path else ([url_path] if url_path else [])
        if not paths:
            raise InstallError("请通过 --path 或 URL 路径指定 skill 位置。")
        return Source(owner=owner, repo=repo, ref=ref, paths=paths)

    if not args.repo:
        raise InstallError("请提供 --repo 或 --url。")
    if "://" in args.repo:
        return resolve_source(Args(url=args.repo, path=args.path, ref=args.ref))
    repo_parts = [part for part in args.repo.split("/") if part]
    if len(repo_parts) != 2:
        raise InstallError("--repo 需要使用 owner/repo 格式。")
    if not args.path:
        raise InstallError("使用 --repo 时必须提供 --path。")
    return Source(owner=repo_parts[0], repo=repo_parts[1], ref=args.ref, paths=list(args.path))


def parse_args(argv: list[str]) -> Args:
    parser = argparse.ArgumentParser(description="从 GitHub 安装 skill 到当前项目，并自动本地化为中文薄 skill。")
    parser.add_argument("--repo", help="owner/repo")
    parser.add_argument("--url", help="GitHub URL，可直接带 tree/ref/path")
    parser.add_argument("--path", nargs="+", help="skill 在仓库里的相对路径，可传多个")
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--dest", help="目标 skill 根目录，默认当前项目 /.agents/skills")
    parser.add_argument("--name", help="本地 skill 中文名称；安装单个 skill 时强烈建议显式传入")
    parser.add_argument("--method", choices=["auto", "download", "git"], default="auto")
    return parser.parse_args(argv, namespace=Args())


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    if args.name and args.path and len(args.path) > 1:
        print("一次安装多个 skill 时不能共享同一个 --name。", file=sys.stderr)
        return 1

    try:
        source = resolve_source(args)
        for path in source.paths:
            validate_relative_path(path)
        dest_root = Path(args.dest).resolve() if args.dest else DEFAULT_DEST
        dest_root.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=temp_root()) as tmp_dir:
            repo_root = Path(prepare_repo(source, args.method, tmp_dir))
            installed_paths: list[Path] = []
            for source_path in source.paths:
                local_source_dir = repo_root / Path(source_path)
                validate_skill_dir(local_source_dir)
                installed_paths.append(
                    localize_installed_skill(source, source_path, local_source_dir, dest_root, args.name)
                )
    except InstallError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1

    for installed in installed_paths:
        print(f"installed={installed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
