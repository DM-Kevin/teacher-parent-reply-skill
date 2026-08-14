import importlib.util
import json
import subprocess
import sys
from datetime import date
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


def test_create_and_find_student(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")

    created = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    matches = manager.find_students(data_root, "张三", "三年级", "2班")

    assert created.student_id == "S0001"
    assert matches == [created]
    assert (data_root / "学生档案" / created.directory / "当前概况.md").exists()
    assert (data_root / "学生档案" / created.directory / "沟通记录").is_dir()


def test_same_name_same_class_gets_student_id_suffix(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    first = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    second = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    assert first.directory == "张三-三年级2班"
    assert second.directory == "张三-三年级2班-S0002"
    assert len(manager.find_students(data_root, "张三")) == 2


def test_create_requires_explicit_confirmation(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")

    with pytest.raises(manager.ArchiveError, match="教师确认"):
        manager.create_student(data_root, "张三", "三年级", "2班", confirmed=False)


def test_student_fields_reject_path_separators(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")

    with pytest.raises(manager.ArchiveError, match="非法字符"):
        manager.create_student(data_root, "张/三", "三年级", "2班", confirmed=True)


def test_validate_rejects_missing_student_directory(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    (data_root / "学生档案" / student.directory).rename(tmp_path / "moved")

    result = manager.validate_archive(data_root)

    assert result["valid"] is False
    assert result["errors"] == [f"索引中的学生目录不存在：{student.directory}"]


def test_promote_student_renames_directory_and_updates_index(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    promoted = manager.promote_student(
        data_root, student.student_id, "四年级", "1班", confirmed=True
    )

    assert promoted.directory == "张三-四年级1班"
    assert not (data_root / "学生档案" / student.directory).exists()
    assert (data_root / "学生档案" / promoted.directory).exists()
    profile = (
        data_root / "学生档案" / promoted.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
    assert "- 年级：四年级" in profile
    assert "- 班级：1班" in profile


def test_promote_student_refreshes_profile_update_date(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    profile_path = data_root / "学生档案" / student.directory / "当前概况.md"
    profile_path.write_text(
        profile_path.read_text(encoding="utf-8").replace(
            f"- {date.today().isoformat()}\n", "- 2020-01-01\n"
        ),
        encoding="utf-8",
    )

    promoted = manager.promote_student(
        data_root, student.student_id, "四年级", "1班", confirmed=True
    )

    updated_profile = (
        data_root / "学生档案" / promoted.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
    assert f"## 信息更新时间\n\n- {date.today().isoformat()}" in updated_profile
