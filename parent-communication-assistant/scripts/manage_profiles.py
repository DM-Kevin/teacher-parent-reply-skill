#!/usr/bin/env python3
"""管理家长沟通助手的本地 Markdown 档案。

本脚本只负责目录、索引、备份和文件写入等确定性操作。沟通策略、家长
心理判断以及回复生成必须由调用它的智能体完成，避免把模型判断偷偷写入
长期档案。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import date, datetime
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

INDEX_HEADER = """# 学生索引

| 编号 | 姓名 | 年级 | 班级 | 目录 | 最近更新 |
|---|---|---|---|---|---|
"""

STUDENT_ID_RE = re.compile(r"^S\d{4}$")
VALID_GRADES = {"一年级", "二年级", "三年级", "四年级", "五年级", "六年级"}
FORBIDDEN_FIELD_CHARS = {"|", "/", "\\", "\n", "\r"}


class ArchiveError(RuntimeError):
    """表示可以直接向教师说明的档案操作错误。"""


@dataclass(frozen=True)
class StudentRecord:
    """学生索引中的一条不可变记录。"""

    student_id: str
    name: str
    grade: str
    class_name: str
    directory: str
    updated_at: str


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


def _index_path(data_root: Path) -> Path:
    """返回学生索引的固定位置。"""
    return data_root.expanduser().resolve() / "学生档案" / "学生索引.md"


def _validate_plain_field(value: str, field_name: str) -> str:
    """校验会进入 Markdown 表格或目录名的短文本，防止结构和路径注入。"""
    normalized = value.strip()
    if not normalized:
        raise ArchiveError(f"{field_name}不能为空。")
    if any(char in normalized for char in FORBIDDEN_FIELD_CHARS):
        raise ArchiveError(f"{field_name}包含非法字符。")
    return normalized


def _validate_student_record(record: StudentRecord) -> None:
    """校验一条索引记录的格式，不检查目录是否真的存在。"""
    if not STUDENT_ID_RE.fullmatch(record.student_id):
        raise ArchiveError(f"学生编号格式错误：{record.student_id}")
    _validate_plain_field(record.name, "学生姓名")
    if record.grade not in VALID_GRADES:
        raise ArchiveError(f"年级不在小学一至六年级范围内：{record.grade}")
    _validate_plain_field(record.class_name, "班级")
    _validate_plain_field(record.directory, "学生目录")
    try:
        date.fromisoformat(record.updated_at)
    except ValueError as exc:
        raise ArchiveError(f"索引日期格式错误：{record.updated_at}") from exc


def load_index(data_root: Path) -> list[StudentRecord]:
    """读取固定六列表格；任何格式异常都阻止后续写入。"""
    path = _index_path(data_root)
    if not path.is_file():
        raise ArchiveError("学生索引不存在，请先初始化或修复档案。")

    records: list[StudentRecord] = []
    seen_ids: set[str] = set()
    seen_directories: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if cells[0] == "编号" or all(cell and set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != 6:
            raise ArchiveError(f"学生索引第 {line_number} 行不是固定六列。")
        record = StudentRecord(*cells)
        _validate_student_record(record)
        if record.student_id in seen_ids:
            raise ArchiveError(f"学生索引存在重复编号：{record.student_id}")
        if record.directory in seen_directories:
            raise ArchiveError(f"学生索引存在重复目录：{record.directory}")
        seen_ids.add(record.student_id)
        seen_directories.add(record.directory)
        records.append(record)
    return records


def _render_index(records: list[StudentRecord]) -> str:
    """按学生编号稳定排序，生成唯一格式的可读 Markdown 索引。"""
    rows = [INDEX_HEADER.rstrip("\n")]
    for record in sorted(records, key=lambda item: item.student_id):
        rows.append(
            "| {student_id} | {name} | {grade} | {class_name} | {directory} | "
            "{updated_at} |".format(**record.__dict__)
        )
    return "\n".join(rows) + "\n"


def _find_by_id(records: list[StudentRecord], student_id: str) -> StudentRecord:
    """按稳定编号查找学生，找不到时给出可理解的错误。"""
    for record in records:
        if record.student_id == student_id:
            return record
    raise ArchiveError(f"未找到学生编号：{student_id}")


def find_students(
    data_root: Path,
    name: str,
    grade: str | None = None,
    class_name: str | None = None,
) -> list[StudentRecord]:
    """精确匹配学生；返回全部候选，不替教师猜测同名身份。"""
    normalized_name = name.strip()
    normalized_grade = grade.strip() if grade is not None else None
    normalized_class = class_name.strip() if class_name is not None else None
    return [
        record
        for record in load_index(data_root)
        if record.name == normalized_name
        and (normalized_grade is None or record.grade == normalized_grade)
        and (normalized_class is None or record.class_name == normalized_class)
    ]


def _next_student_id(records: list[StudentRecord]) -> str:
    """从现有最大编号递增生成新编号；支持流程不提供删除或复用编号。"""
    highest = max((int(item.student_id[1:]) for item in records), default=0)
    next_number = highest + 1
    if next_number > 9999:
        raise ArchiveError("学生编号已经达到 S9999，无法继续自动编号。")
    return f"S{next_number:04d}"


def _current_profile_template(record: StudentRecord) -> str:
    """创建仅含已知基本信息的概况，不补造任何学生或家长特征。"""
    return f"""# 当前概况

## 基本信息

- 学生编号：{record.student_id}
- 姓名：{record.name}
- 年级：{record.grade}
- 班级：{record.class_name}

## 已确认的长期表现

- 暂无长期结论。

## 已采取的支持措施

- 暂无已确认措施。

## 家长关注点与沟通偏好

- 暂无已确认偏好。

## 尚未解决的问题

- 暂无。

## 最近一次沟通结论

- 暂无。

## 信息更新时间

- {record.updated_at}
"""


def create_student(
    data_root: Path,
    name: str,
    grade: str,
    class_name: str,
    confirmed: bool,
) -> StudentRecord:
    """在教师确认后创建学生目录，并以一次事务更新可读索引。"""
    if not confirmed:
        raise ArchiveError("创建学生档案前必须获得教师确认。")
    normalized_name = _validate_plain_field(name, "学生姓名")
    normalized_grade = grade.strip()
    if normalized_grade not in VALID_GRADES:
        raise ArchiveError("年级必须是一年级至六年级。")
    normalized_class = _validate_plain_field(class_name, "班级")

    resolved_root = data_root.expanduser().resolve()
    records = load_index(resolved_root)
    student_id = _next_student_id(records)
    base_directory = f"{normalized_name}-{normalized_grade}{normalized_class}"
    directory = base_directory
    student_root = resolved_root / "学生档案" / directory
    if student_root.exists():
        directory = f"{base_directory}-{student_id}"
        student_root = resolved_root / "学生档案" / directory
    if student_root.exists():
        raise ArchiveError(f"学生目录已经存在：{directory}")

    today = date.today().isoformat()
    record = StudentRecord(
        student_id,
        normalized_name,
        normalized_grade,
        normalized_class,
        directory,
        today,
    )
    _validate_student_record(record)

    try:
        (student_root / "沟通记录").mkdir(parents=True)
        atomic_write_text(
            student_root / "当前概况.md",
            _current_profile_template(record),
            resolved_root,
            backup=False,
        )
        atomic_write_text(
            _index_path(resolved_root),
            _render_index([*records, record]),
            resolved_root,
        )
    except Exception:
        # 只回滚本次新建且此前不存在的精确目录，绝不删除其他档案。
        if student_root.exists():
            shutil.rmtree(student_root)
        raise
    return record


def validate_archive(data_root: Path) -> dict[str, object]:
    """只读校验索引和学生目录一致性，返回适合展示的错误清单。"""
    resolved_root = data_root.expanduser().resolve()
    errors: list[str] = []
    try:
        records = load_index(resolved_root)
    except (ArchiveError, OSError) as exc:
        return {"valid": False, "errors": [str(exc)], "student_count": 0}

    for record in records:
        student_root = resolved_root / "学生档案" / record.directory
        if not student_root.is_dir():
            errors.append(f"索引中的学生目录不存在：{record.directory}")
            continue
        if not (student_root / "当前概况.md").is_file():
            errors.append(f"学生概况不存在：{record.directory}/当前概况.md")
        if not (student_root / "沟通记录").is_dir():
            errors.append(f"沟通记录目录不存在：{record.directory}/沟通记录")

    return {
        "valid": not errors,
        "errors": errors,
        "student_count": len(records),
    }


def _replace_profile_field(content: str, label: str, value: str) -> str:
    """只替换固定基本信息行；缺失字段说明档案结构已损坏。"""
    pattern = re.compile(rf"^- {re.escape(label)}：.*$", re.MULTILINE)
    updated, count = pattern.subn(f"- {label}：{value}", content, count=1)
    if count != 1:
        raise ArchiveError(f"当前概况缺少固定字段：{label}")
    return updated


def _replace_section_first_bullet(content: str, heading: str, value: str) -> str:
    """替换固定章节的首条项目，避免用全局字符串替换误伤其他日期。"""
    pattern = re.compile(rf"({re.escape(heading)}\n\n)- [^\n]*")
    updated, count = pattern.subn(rf"\1- {value}", content, count=1)
    if count != 1:
        raise ArchiveError(f"当前概况缺少固定章节：{heading}")
    return updated


def promote_student(
    data_root: Path,
    student_id: str,
    grade: str,
    class_name: str,
    confirmed: bool,
) -> StudentRecord:
    """在确认后更新年级班级，并在任一步失败时恢复旧目录和索引。"""
    if not confirmed:
        raise ArchiveError("更新年级班级前必须获得教师确认。")
    normalized_grade = grade.strip()
    if normalized_grade not in VALID_GRADES:
        raise ArchiveError("年级必须是一年级至六年级。")
    normalized_class = _validate_plain_field(class_name, "班级")

    resolved_root = data_root.expanduser().resolve()
    records = load_index(resolved_root)
    current = _find_by_id(records, student_id)
    old_root = resolved_root / "学生档案" / current.directory
    if not old_root.is_dir():
        raise ArchiveError(f"学生目录不存在：{current.directory}")

    base_directory = f"{current.name}-{normalized_grade}{normalized_class}"
    new_directory = base_directory
    new_root = resolved_root / "学生档案" / new_directory
    if new_root.exists() and new_root != old_root:
        new_directory = f"{base_directory}-{current.student_id}"
        new_root = resolved_root / "学生档案" / new_directory
    if new_root.exists() and new_root != old_root:
        raise ArchiveError(f"目标学生目录已经存在：{new_directory}")

    updated = StudentRecord(
        current.student_id,
        current.name,
        normalized_grade,
        normalized_class,
        new_directory,
        date.today().isoformat(),
    )
    old_index_text = _index_path(resolved_root).read_text(encoding="utf-8")
    old_profile_path = old_root / "当前概况.md"
    old_profile_text = old_profile_path.read_text(encoding="utf-8")
    new_profile_text = _replace_profile_field(old_profile_text, "年级", normalized_grade)
    new_profile_text = _replace_profile_field(new_profile_text, "班级", normalized_class)
    new_profile_text = _replace_section_first_bullet(
        new_profile_text, "## 信息更新时间", updated.updated_at
    )
    updated_records = [updated if item.student_id == student_id else item for item in records]

    renamed = False
    try:
        if new_root != old_root:
            old_root.rename(new_root)
            renamed = True
        atomic_write_text(
            new_root / "当前概况.md", new_profile_text, resolved_root
        )
        atomic_write_text(
            _index_path(resolved_root), _render_index(updated_records), resolved_root
        )
    except Exception:
        # 使用内存中的旧内容回滚，避免恢复逻辑依赖备份目录的时间戳。
        current_root = new_root if renamed else old_root
        if current_root.exists():
            _replace_text_without_backup(current_root / "当前概况.md", old_profile_text)
        if renamed and new_root.exists() and not old_root.exists():
            new_root.rename(old_root)
        _replace_text_without_backup(_index_path(resolved_root), old_index_text)
        raise
    return updated
