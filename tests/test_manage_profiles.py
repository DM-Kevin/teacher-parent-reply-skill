import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "parent-communication-assistant" / "scripts" / "manage_profiles.py"


def load_manager():
    """从带连字符的 Skill 目录加载脚本模块，供测试真实函数。"""
    spec = importlib.util.spec_from_file_location("manage_profiles", SCRIPT_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


manager = load_manager()


def test_manager_script_can_run_without_arguments():
    """脚本入口损坏或文件缺失时，这个测试必须立即失败。"""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_initialize_archive_creates_required_files(tmp_path):
    data_root = tmp_path / "家长沟通档案"
    settings_path = tmp_path / ".parent-communication-assistant" / "settings.json"

    result = manager.initialize_archive(data_root, settings_path)

    assert result["schema_version"] == 1
    assert (data_root / "教师档案" / "表达偏好.md").exists()
    assert (data_root / "教师档案" / "已确认表达样本.md").exists()
    assert (data_root / "学生档案" / "学生索引.md").exists()
    assert json.loads(settings_path.read_text(encoding="utf-8")) == {
        "data_root": str(data_root.resolve()),
        "schema_version": 1,
    }


def test_load_settings_rejects_missing_data_root(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps({"data_root": str(tmp_path / "missing"), "schema_version": 1}),
        encoding="utf-8",
    )

    with pytest.raises(manager.ArchiveError, match="档案目录不存在"):
        manager.load_settings(settings_path)


def test_initialize_archive_refuses_unknown_nonempty_directory(tmp_path):
    data_root = tmp_path / "existing"
    data_root.mkdir()
    marker = data_root / "原有文件.txt"
    marker.write_text("不得覆盖", encoding="utf-8")

    with pytest.raises(manager.ArchiveError, match="不是有效的家长沟通档案"):
        manager.initialize_archive(data_root, tmp_path / "settings.json")

    assert marker.read_text(encoding="utf-8") == "不得覆盖"


def test_initialize_archive_preserves_complete_existing_archive(tmp_path):
    data_root = tmp_path / "archive"
    first_settings = tmp_path / "first-settings.json"
    manager.initialize_archive(data_root, first_settings)
    preference = data_root / "教师档案" / "表达偏好.md"
    preference.write_text("# 表达偏好\n\n保留内容\n", encoding="utf-8")

    second_settings = tmp_path / "second-settings.json"
    manager.initialize_archive(data_root, second_settings)

    assert preference.read_text(encoding="utf-8") == "# 表达偏好\n\n保留内容\n"
    assert json.loads(second_settings.read_text(encoding="utf-8"))["data_root"] == str(
        data_root.resolve()
    )


def test_atomic_write_restores_original_when_replace_fails(tmp_path, monkeypatch):
    data_root = tmp_path / "archive"
    target = data_root / "学生档案" / "学生索引.md"
    target.parent.mkdir(parents=True)
    target.write_text("旧内容", encoding="utf-8")

    def fail_replace(source, destination):
        raise OSError("simulated failure")

    monkeypatch.setattr(manager.os, "replace", fail_replace)

    with pytest.raises(manager.ArchiveError, match="写入失败"):
        manager.atomic_write_text(target, "新内容", data_root)

    assert target.read_text(encoding="utf-8") == "旧内容"


def test_atomic_write_creates_recoverable_backup(tmp_path):
    data_root = tmp_path / "archive"
    target = data_root / "学生档案" / "学生索引.md"
    target.parent.mkdir(parents=True)
    target.write_text("旧内容", encoding="utf-8")

    manager.atomic_write_text(target, "新内容", data_root)

    backups = list((data_root / ".backups").glob("*/学生档案/学生索引.md"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "旧内容"
    assert target.read_text(encoding="utf-8") == "新内容"
