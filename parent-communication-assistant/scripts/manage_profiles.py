#!/usr/bin/env python3
"""管理家长沟通助手的本地 Markdown 档案。

本脚本只负责目录、索引、备份和文件写入等确定性操作。沟通策略、家长
心理判断以及回复生成必须由调用它的智能体完成，避免把模型判断偷偷写入
长期档案。
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 1
SETTINGS_DIR_NAME = ".parent-communication-assistant"
SETTINGS_FILE_NAME = "settings.json"

TEACHER_PREFERENCE_INITIAL = """# 表达偏好

尚未初始化。请先由教师确认表达偏好，再写入本文件。
"""

CONFIRMED_SAMPLES_INITIAL = """# 已确认表达样本

尚无经教师确认的表达样本。
"""

STUDENT_INDEX_INITIAL = """# 学生索引

| 编号 | 姓名 | 年级 | 班级 | 目录 | 最近更新 |
|---|---|---|---|---|---|
"""


class ArchiveError(RuntimeError):
    """表示可以直接向教师说明的档案操作错误。"""


def default_settings_path() -> Path:
    """返回只保存档案路径和结构版本的用户级设置文件位置。"""
    return Path.home() / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME


def default_data_root() -> Path:
    """返回首次初始化时建议使用的本地档案目录。"""
    return Path.home() / "Documents" / "家长沟通档案"


def _replace_text_without_backup(path: Path, content: str) -> None:
    """在同目录写临时文件后原子替换，失败时保留旧设置。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=path.parent,
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise ArchiveError(f"设置保存失败，旧设置已保留：{exc}") from exc


def save_settings(data_root: Path, settings_path: Path | None = None) -> Path:
    """保存档案根目录；设置文件不得包含学生或家长信息。"""
    resolved_root = data_root.expanduser().resolve()
    target = (settings_path or default_settings_path()).expanduser()
    payload = {
        "data_root": str(resolved_root),
        "schema_version": SCHEMA_VERSION,
    }
    _replace_text_without_backup(
        target,
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    )
    return target


def load_settings(settings_path: Path | None = None) -> dict[str, object]:
    """读取并验证设置；路径失效时不擅自新建另一套档案。"""
    target = (settings_path or default_settings_path()).expanduser()
    if not target.is_file():
        raise ArchiveError("尚未初始化档案目录，请先选择保存位置。")

    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"设置文件无法读取：{exc}") from exc

    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ArchiveError("档案版本不兼容，请先完成数据迁移。")

    raw_root = payload.get("data_root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise ArchiveError("设置文件缺少有效的档案目录。")
    data_root = Path(raw_root).expanduser()
    if not data_root.is_dir():
        raise ArchiveError("档案目录不存在，请重新选择保存位置。")

    return {
        "data_root": str(data_root.resolve()),
        "schema_version": SCHEMA_VERSION,
    }


def _required_archive_files(data_root: Path) -> tuple[Path, Path, Path]:
    """集中定义首版档案必须存在的三个入口文件。"""
    return (
        data_root / "教师档案" / "表达偏好.md",
        data_root / "教师档案" / "已确认表达样本.md",
        data_root / "学生档案" / "学生索引.md",
    )


def _has_complete_initial_structure(data_root: Path) -> bool:
    """只检查初始化结构是否完整；深层索引一致性由后续校验负责。"""
    return all(path.is_file() for path in _required_archive_files(data_root))


def initialize_archive(
    data_root: Path,
    settings_path: Path | None = None,
) -> dict[str, object]:
    """初始化空档案，或安全连接一套已经存在的完整档案。"""
    resolved_root = data_root.expanduser().resolve()

    if resolved_root.exists() and not resolved_root.is_dir():
        raise ArchiveError("所选档案位置不是目录。")

    if resolved_root.is_dir() and any(resolved_root.iterdir()):
        if not _has_complete_initial_structure(resolved_root):
            raise ArchiveError(
                "所选目录不是有效的家长沟通档案，请选择空目录或已有完整档案。"
            )
        save_settings(resolved_root, settings_path)
        return {
            "data_root": str(resolved_root),
            "schema_version": SCHEMA_VERSION,
        }

    resolved_root.mkdir(parents=True, exist_ok=True)
    initial_documents = (
        (_required_archive_files(resolved_root)[0], TEACHER_PREFERENCE_INITIAL),
        (_required_archive_files(resolved_root)[1], CONFIRMED_SAMPLES_INITIAL),
        (_required_archive_files(resolved_root)[2], STUDENT_INDEX_INITIAL),
    )
    for path, content in initial_documents:
        atomic_write_text(path, content, resolved_root, backup=False)

    save_settings(resolved_root, settings_path)
    return {
        "data_root": str(resolved_root),
        "schema_version": SCHEMA_VERSION,
    }


def atomic_write_text(
    path: Path,
    content: str,
    data_root: Path,
    backup: bool = True,
) -> Path | None:
    """安全写入档案文件，并在覆盖前创建保持相对路径的可恢复备份。"""
    resolved_root = data_root.expanduser().resolve()
    resolved_target = path.expanduser().resolve()
    try:
        relative_target = resolved_target.relative_to(resolved_root)
    except ValueError as exc:
        raise ArchiveError("拒绝写入档案根目录之外的文件。") from exc

    resolved_target.parent.mkdir(parents=True, exist_ok=True)
    if resolved_target.is_file():
        try:
            if resolved_target.read_text(encoding="utf-8") == content:
                return None
        except OSError as exc:
            raise ArchiveError(f"原文件无法读取：{exc}") from exc

    backup_path: Path | None = None
    if backup and resolved_target.is_file():
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S%f")
        backup_path = resolved_root / ".backups" / stamp / relative_target
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(resolved_target, backup_path)
        except OSError as exc:
            raise ArchiveError(f"备份失败，未修改原文件：{exc}") from exc

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            delete=False,
            dir=resolved_target.parent,
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        os.replace(temp_path, resolved_target)
    except Exception as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise ArchiveError(f"写入失败，原文件已保留：{exc}") from exc

    return backup_path
