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


def test_load_settings_rejects_non_object_json_with_archive_error(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[]\n", encoding="utf-8")

    with pytest.raises(manager.ArchiveError, match="必须是 JSON 对象"):
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


def test_initialize_archive_rolls_back_partial_structure_when_replace_fails(
    tmp_path, monkeypatch
):
    data_root = tmp_path / "archive"
    settings_path = tmp_path / "settings.json"
    real_replace = manager.os.replace
    calls = 0

    def fail_second_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated failure")
        return real_replace(source, destination)

    monkeypatch.setattr(manager.os, "replace", fail_second_replace)

    with pytest.raises(manager.ArchiveError):
        manager.initialize_archive(data_root, settings_path)

    assert not data_root.exists()
    monkeypatch.setattr(manager.os, "replace", real_replace)
    manager.initialize_archive(data_root, settings_path)
    assert manager.validate_archive(data_root)["valid"] is True


def test_initialize_archive_rejects_skill_install_directory():
    skill_root = manager.Path(manager.__file__).resolve().parents[1]

    with pytest.raises(manager.ArchiveError, match="Skill 安装目录"):
        manager.initialize_archive(skill_root)


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


def test_validate_rejects_malformed_index_row_and_orphan_directory(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    index_path = data_root / "学生档案" / "学生索引.md"
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace("| S0001 |", "S0001 |"),
        encoding="utf-8",
    )

    malformed = manager.validate_archive(data_root)
    assert malformed["valid"] is False
    assert "必须是六列表格行" in malformed["errors"][0]

    index_path.write_text(manager.STUDENT_INDEX_INITIAL, encoding="utf-8")
    orphan = manager.validate_archive(data_root)
    assert orphan["valid"] is False
    assert f"未被索引引用的学生目录：{student.directory}" in orphan["errors"]


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


def test_promote_student_restores_directory_when_replace_keeps_failing(
    tmp_path, monkeypatch
):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    def fail_replace(source, destination):
        raise OSError("persistent failure")

    monkeypatch.setattr(manager.os, "replace", fail_replace)

    with pytest.raises(manager.ArchiveError):
        manager.promote_student(
            data_root, student.student_id, "四年级", "1班", confirmed=True
        )

    assert (data_root / "学生档案" / student.directory).is_dir()
    assert not (data_root / "学生档案" / "张三-四年级1班").exists()
    assert manager.validate_archive(data_root)["valid"] is True


def test_promote_student_restores_profile_when_index_replace_keeps_failing(
    tmp_path, monkeypatch
):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    original_profile = (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
    real_replace = manager.os.replace
    calls = 0

    def fail_after_profile_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError("persistent failure after profile write")
        return real_replace(source, destination)

    monkeypatch.setattr(manager.os, "replace", fail_after_profile_replace)

    with pytest.raises(manager.ArchiveError):
        manager.promote_student(
            data_root, student.student_id, "四年级", "1班", confirmed=True
        )

    restored_profile = (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
    assert restored_profile == original_profile
    assert manager.validate_archive(data_root)["valid"] is True


def complete_current_profile(student_id="S0001"):
    """返回手工写明预期字段的测试概况，不复用生产模板。"""
    return f"""# 当前概况

## 基本信息

- 学生编号：{student_id}
- 姓名：张三
- 年级：三年级
- 班级：2班

## 已确认的长期表现

- 暂无长期结论。

## 已采取的支持措施

- 教师在课堂结束前提醒记录作业。

## 家长关注点与沟通偏好

- 偏好简短、具体的沟通。

## 尚未解决的问题

- 继续观察作业记录情况。

## 最近一次沟通结论

- 先由教师课堂提醒一周。

## 信息更新时间

- 2020-01-01
"""


def complete_communication_record():
    """返回包含所有必填章节的沟通记录。"""
    return """# 沟通记录

## 日期与渠道

- 日期：2026-08-14
- 渠道：微信

## 本次问题

- 主题：作业完成问题

## 已确认事实

- 当天作业未完成。

## 家长核心关注

- 不希望额外增加压力。

## 教师实际回应

- 说明本次补做不是额外加量。

## 达成共识

- 先由教师在课堂提醒。

## 待跟进事项

- 一周后观察完成情况。

## 是否更新长期概况

- 是否更新：是
- 拟更新：已采取的支持措施。
"""


def test_write_current_profile_requires_confirmation(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    original = (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8")

    with pytest.raises(manager.ArchiveError, match="教师确认"):
        manager.write_current_profile(
            data_root, student.student_id, complete_current_profile(), confirmed=False
        )

    assert (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8") == original


def test_write_current_profile_rejects_mismatched_student(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    with pytest.raises(manager.ArchiveError, match="基本信息与索引不一致"):
        manager.write_current_profile(
            data_root,
            student.student_id,
            complete_current_profile().replace("- 姓名：张三", "- 姓名：李四"),
            confirmed=True,
        )


def test_write_current_profile_refreshes_profile_and_index_date(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    manager.write_current_profile(
        data_root, student.student_id, complete_current_profile(), confirmed=True
    )

    profile = (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
    assert f"## 信息更新时间\n\n- {date.today().isoformat()}" in profile
    assert manager.find_students(data_root, "张三")[0].updated_at == date.today().isoformat()


def test_write_current_profile_restores_content_when_index_write_fails(
    tmp_path, monkeypatch
):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    profile_path = data_root / "学生档案" / student.directory / "当前概况.md"
    original_profile = profile_path.read_text(encoding="utf-8")
    index_path = data_root / "学生档案" / "学生索引.md"
    index_path.write_text(
        index_path.read_text(encoding="utf-8").replace(
            date.today().isoformat(), "2020-01-01"
        ),
        encoding="utf-8",
    )
    real_replace = manager.os.replace
    calls = 0

    def fail_after_profile_replace(source, destination):
        nonlocal calls
        calls += 1
        if calls >= 2:
            raise OSError("persistent failure after profile write")
        return real_replace(source, destination)

    monkeypatch.setattr(manager.os, "replace", fail_after_profile_replace)

    with pytest.raises(manager.ArchiveError):
        manager.write_current_profile(
            data_root, student.student_id, complete_current_profile(), confirmed=True
        )

    assert profile_path.read_text(encoding="utf-8") == original_profile
    assert manager.validate_archive(data_root)["valid"] is True


def test_save_communication_creates_unique_record_and_updates_date(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    content = complete_communication_record()

    first = manager.save_communication(
        data_root,
        student.student_id,
        "2026-08-14",
        "微信",
        "作业完成问题",
        content,
        True,
    )
    second = manager.save_communication(
        data_root,
        student.student_id,
        "2026-08-14",
        "微信",
        "作业完成问题",
        content,
        True,
    )

    assert first.name == "2026-08-14-作业完成问题.md"
    assert second.name == "2026-08-14-作业完成问题-02.md"
    assert manager.find_students(data_root, "张三")[0].updated_at == "2026-08-14"


def test_save_communication_rejects_mismatched_channel(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    with pytest.raises(manager.ArchiveError, match="渠道与命令参数不一致"):
        manager.save_communication(
            data_root,
            student.student_id,
            "2026-08-14",
            "电话",
            "作业完成问题",
            complete_communication_record(),
            True,
        )


def test_save_communication_rejects_mismatched_topic_and_invalid_update_flag(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    with pytest.raises(manager.ArchiveError, match="主题与命令参数不一致"):
        manager.save_communication(
            data_root,
            student.student_id,
            "2026-08-14",
            "微信",
            "课堂表现",
            complete_communication_record(),
            True,
        )

    invalid_flag = complete_communication_record().replace(
        "- 是否更新：是", "- 是否更新：可能"
    )
    with pytest.raises(manager.ArchiveError, match="只能填写“是”或“否”"):
        manager.save_communication(
            data_root,
            student.student_id,
            "2026-08-14",
            "微信",
            "作业完成问题",
            invalid_flag,
            True,
        )


def test_write_teacher_profile_requires_headings_and_confirmation(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    content = """# 表达偏好

## 常用称呼
- 学生姓名加“妈妈”或“爸爸”。

## 回复长度
- 通常一个微信气泡。

## 语气与直接程度
- 自然、简短。

## 语气词与表情
- 偶尔使用“哈”。

## 开场与收尾
- 直接说明事情，最后确认下一步。

## 避免表达
- 避免论文式概念。
"""

    with pytest.raises(manager.ArchiveError, match="教师确认"):
        manager.write_teacher_profile(data_root, content, confirmed=False)

    path = manager.write_teacher_profile(data_root, content, confirmed=True)
    assert path.read_text(encoding="utf-8") == content


def test_confirmed_samples_reject_more_than_ten(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    content = "# 已确认表达样本\n\n" + "\n".join(
        f"## 样本 {number}\n\n- 内容 {number}" for number in range(1, 12)
    )

    with pytest.raises(manager.ArchiveError, match="最多保留 10 条"):
        manager.write_confirmed_samples(data_root, content, confirmed=True)


def test_cli_returns_json_for_find(tmp_path, capsys):
    settings_path = tmp_path / "settings.json"
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, settings_path)
    manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    exit_code = manager.main(
        ["--settings", str(settings_path), "find", "--name", "张三"]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["students"][0]["student_id"] == "S0001"


def test_cli_returns_json_error_for_non_object_settings(tmp_path, capsys):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[]\n", encoding="utf-8")

    exit_code = manager.main(["--settings", str(settings_path), "validate"])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "ok": False,
        "error": "设置文件顶层必须是 JSON 对象。",
    }
