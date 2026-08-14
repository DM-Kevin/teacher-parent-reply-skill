# Parent Communication Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个覆盖小学一至六年级、能够准备家长沟通、生成自然回复、判断是否应结束对话并在教师确认后维护本地档案的 Codex Skill。

**Architecture:** 使用精简的 `SKILL.md` 编排交互，按需加载四份领域参考资料；使用单个标准库 Python 脚本完成档案初始化、学生检索、建档、更新、备份和一致性校验。真实档案位于 Skill 目录外，Markdown 对教师可读，所有长期写入必须经过显式确认。

**Tech Stack:** Codex Skill、Markdown、Python 3.10+ 标准库、pytest 8+、YAML 元数据生成与 Skill 校验脚本。

## Global Constraints

- Skill 名称固定为 `parent-communication-assistant`，目录名与 frontmatter `name` 完全一致。
- 真实档案不得保存在 Skill 安装目录内；默认档案根目录为 `Path.home() / "Documents" / "家长沟通档案"`。
- 设置文件固定为 `Path.home() / ".parent-communication-assistant" / "settings.json"`，只保存 `data_root` 和 `schema_version`。
- 数据结构版本首版固定为 `1`。
- 脚本只使用 Python 标准库；不得引入数据库、云端同步、微信读取或自动发送能力。
- Python 最低版本为 3.10；测试使用 pytest 8+。
- 所有 Python 代码注释和 docstring 使用中文且尽量详细。
- 所有新增 Markdown 文件使用 UTF-8 和中文正文。
- 微信建议回复默认 60～120 个汉字等可见字符，复杂情况不得超过约 180 字，除非教师明确要求展开。
- 所有学生档案、沟通总结和教师表达偏好写入前必须获得教师确认。
- 不保存身份证号、家庭住址、电话号码等与沟通无关的敏感信息；截图和完整原始聊天默认不落盘。
- 不虚构学生表现，不将主观判断写成事实，不对学生或家长作心理诊断或人格标签。

## Execution Corrections

本节覆盖下文与其冲突的测试步骤：

- 不使用搜索 `SKILL.md` 或 reference 文件固定文字的方式证明 Skill 有效；这类静态断言不能验证模型行为。
- 不创建或保留 `tests/test_skill_contract.py`。Skill 包结构和 frontmatter 使用官方 `quick_validate.py` 校验。
- 在编写 `SKILL.md` 和领域 references 前，先用三个新鲜、无 Skill 的代理场景建立行为基线，并将原始输出保存到 `tests/evaluations/baseline.md`。
- 完成 Skill 后，用三个同源场景在新鲜上下文中复测，将原始输出与逐项评分保存到 `tests/evaluations/with-skill.md`。
- Task 1 中关于 `tests/test_skill_contract.py` 的步骤由“运行官方校验并确认骨架有效”替代。
- Task 5 和 Task 6 中关于 `tests/test_skill_contract.py` 的步骤由“对照基线失败写最小规则，并在 Task 7 行为复测”替代。
- Python 档案脚本仍严格执行测试先行；`tests/test_manage_profiles.py` 的红—绿循环保持不变。

---

## Planned File Structure

```text
.
├── docs/superpowers/specs/2026-08-14-parent-communication-assistant-design.md
├── docs/superpowers/plans/2026-08-14-parent-communication-assistant.md
├── parent-communication-assistant/
│   ├── SKILL.md
│   ├── agents/
│   │   └── openai.yaml
│   ├── scripts/
│   │   └── manage_profiles.py
│   └── references/
│       ├── communication-strategies.md
│       ├── grade-guidance.md
│       ├── profile-schema.md
│       └── risk-boundaries.md
└── tests/
    ├── evaluations/
    │   ├── baseline.md
    │   └── with-skill.md
    ├── fixtures/
    │   ├── teacher-style-samples.md
    │   └── difficult-parent-case.md
    └── test_manage_profiles.py
```

File responsibilities:

- `parent-communication-assistant/SKILL.md`: 唯一的交互编排入口，决定初始化、预案、陪聊、电话／面谈、结束和确认写入流程。
- `parent-communication-assistant/scripts/manage_profiles.py`: 只处理确定性的本地档案操作，提供 Python API 与 JSON CLI。
- `communication-strategies.md`: 问题分类、家长回应类型、回复动作和微信／电话输出规则。
- `grade-guidance.md`: 一至六年级沟通重点和避免刻板化要求。
- `profile-schema.md`: 所有 Markdown 档案的固定字段、模板、长度和客观表达规则。
- `risk-boundaries.md`: 高风险识别、事实边界、升级学校流程和禁止承诺。
- `test_manage_profiles.py`: 档案脚本的单元测试和故障恢复测试。
- `evaluations/`: 保存无 Skill 基线和加载 Skill 后的新鲜上下文行为结果。

### Task 1: Scaffold a valid Skill package

**Files:**
- Create: `parent-communication-assistant/SKILL.md`
- Create: `parent-communication-assistant/agents/openai.yaml`
- Create: `parent-communication-assistant/scripts/`
- Create: `parent-communication-assistant/references/`
- Create: `tests/test_skill_contract.py`

**Interfaces:**
- Consumes: `/Users/kevin/.codex/skills/.system/skill-creator/scripts/init_skill.py`
- Produces: 可被 Codex 发现的 `parent-communication-assistant` Skill 骨架；后续任务在该目录内填充逻辑。

- [ ] **Step 1: Write the failing structure test**

```python
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "parent-communication-assistant"


def test_skill_package_has_required_structure():
    required = [
        SKILL_DIR / "SKILL.md",
        SKILL_DIR / "agents" / "openai.yaml",
        SKILL_DIR / "scripts",
        SKILL_DIR / "references",
    ]
    assert all(path.exists() for path in required)


def test_skill_frontmatter_name_matches_directory():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    _, frontmatter, _ = text.split("---", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == SKILL_DIR.name
    assert set(metadata) == {"name", "description"}
```

- [ ] **Step 2: Run the structure test and verify it fails**

Run: `uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -v`

Expected: FAIL because `parent-communication-assistant/` does not exist.

- [ ] **Step 3: Initialize the Skill using the official scaffold script**

Run:

```bash
python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/init_skill.py \
  parent-communication-assistant \
  --path . \
  --resources scripts,references \
  --interface 'display_name=家长沟通助手' \
  --interface 'short_description=帮助小学教师准备沟通、生成自然回复并沉淀本地学生档案' \
  --interface 'default_prompt=使用 $parent-communication-assistant 帮我准备并回复这次家长沟通。'
```

Replace the generated `SKILL.md` with this minimal valid package description:

```markdown
---
name: parent-communication-assistant
description: 为小学一至六年级教师准备家长沟通、生成微信回复或电话面谈提纲，并在教师确认后维护本地教师语气与学生沟通档案。用于教师需要主动联系家长、逐轮回复家长消息、判断是否应结束争论、整理沟通结果或查询既往学生沟通背景时。
---

# 家长沟通助手

帮助教师围绕具体事实、家长关注点和下一步行动组织沟通。生成内容时不得虚构学生表现、扩大教师承诺或把主观判断当作事实。
```

- [ ] **Step 4: Verify generated UI metadata**

`agents/openai.yaml` must contain exactly:

```yaml
interface:
  display_name: "家长沟通助手"
  short_description: "帮助小学教师准备沟通、生成自然回复并沉淀本地学生档案"
  default_prompt: "使用 $parent-communication-assistant 帮我准备并回复这次家长沟通。"
```

Run: `uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -v`

Expected: PASS.

- [ ] **Step 5: Run the official Skill validator**

Run: `python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/quick_validate.py parent-communication-assistant`

Expected: validation succeeds with no frontmatter or naming errors.

- [ ] **Step 6: Commit the scaffold**

```bash
git add parent-communication-assistant tests/test_skill_contract.py
git commit -m "chore: scaffold parent communication assistant skill"
```

### Task 2: Implement settings, initialization, and atomic writes

**Files:**
- Create: `parent-communication-assistant/scripts/manage_profiles.py`
- Create: `tests/test_manage_profiles.py`

**Interfaces:**
- Produces: `ArchiveError`, `default_settings_path()`, `default_data_root()`, `save_settings(data_root, settings_path)`, `load_settings(settings_path)`, `initialize_archive(data_root, settings_path)`, and `atomic_write_text(path, content, data_root, backup=True)`.
- Return contract: successful public functions return `pathlib.Path`, an explicitly documented dataclass, or JSON-serializable dictionaries; expected user errors raise `ArchiveError` with a concise Chinese message.

- [ ] **Step 1: Write failing initialization tests**

```python
import json
import importlib.util
import sys
from pathlib import Path

import pytest

def load_manager():
    path = (
        Path(__file__).resolve().parents[1]
        / "parent-communication-assistant"
        / "scripts"
        / "manage_profiles.py"
    )
    spec = importlib.util.spec_from_file_location("manage_profiles", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


manager = load_manager()


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
```

- [ ] **Step 2: Run tests and verify the API is missing**

Run: `uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -v`

Expected: FAIL because `initialize_archive`, `load_settings`, and `atomic_write_text` do not exist.

- [ ] **Step 3: Implement settings and archive initialization**

Implement these exact constants and signatures:

```python
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path


SCHEMA_VERSION = 1
SETTINGS_DIR_NAME = ".parent-communication-assistant"
SETTINGS_FILE_NAME = "settings.json"


class ArchiveError(RuntimeError):
    """表示可向教师说明的档案操作错误。"""


def default_settings_path() -> Path:
    return Path.home() / SETTINGS_DIR_NAME / SETTINGS_FILE_NAME


def default_data_root() -> Path:
    return Path.home() / "Documents" / "家长沟通档案"


def save_settings(data_root: Path, settings_path: Path | None = None) -> Path:
    resolved_root = data_root.expanduser().resolve()
    target = settings_path or default_settings_path()
    payload = {"data_root": str(resolved_root), "schema_version": SCHEMA_VERSION}
    target.parent.mkdir(parents=True, exist_ok=True)
    _replace_text_without_backup(target, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return target


def load_settings(settings_path: Path | None = None) -> dict[str, object]:
    target = settings_path or default_settings_path()
    if not target.exists():
        raise ArchiveError("尚未初始化档案目录，请先选择保存位置。")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ArchiveError("档案版本不兼容，请先完成数据迁移。")
    data_root = Path(str(payload.get("data_root", ""))).expanduser()
    if not data_root.is_dir():
        raise ArchiveError("档案目录不存在，请重新选择保存位置。")
    return {"data_root": str(data_root.resolve()), "schema_version": SCHEMA_VERSION}
```

Implement the private helper used by `save_settings()` before calling it:

```python
def _replace_text_without_backup(path: Path, content: str) -> None:
    """在同目录写入临时文件后原子替换设置文件，失败时不破坏旧设置。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", delete=False, dir=path.parent
        ) as handle:
            handle.write(content)
            temp_path = Path(handle.name)
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)
        raise ArchiveError(f"设置保存失败，旧设置已保留：{exc}") from exc
```

`initialize_archive()` must create these exact initial documents:

```text
教师档案/表达偏好.md
教师档案/已确认表达样本.md
学生档案/学生索引.md
```

The index starts as:

```markdown
# 学生索引

| 编号 | 姓名 | 年级 | 班级 | 目录 | 最近更新 |
|---|---|---|---|---|---|
```

Teacher files start with their title and a sentence saying they are not yet initialized; do not invent preferences or examples.

Implement `_has_complete_initial_structure(data_root)` in Task 2 to check only the three required files and their parent directories. If an existing `data_root` passes that structural check, preserve every file and only refresh settings; deep index validation is added in Task 3. If the directory contains unrelated files or a partial incompatible structure, abort with `ArchiveError("所选目录不是有效的家长沟通档案，请选择空目录或已有完整档案。")`; never overwrite or merge it during initialization.

- [ ] **Step 4: Implement atomic writes and backups**

Implement `atomic_write_text(path, content, data_root, backup=True)` with these exact rules:

1. Resolve both paths and reject targets outside `data_root` using `Path.relative_to()`.
2. Create the parent directory.
3. If the target exists and content changes, copy the old version to `.backups/YYYYMMDD-HHMMSSffffff/<relative-path>`.
4. Write UTF-8 content to a `NamedTemporaryFile(delete=False, dir=target.parent)`.
5. Call `os.replace(temp_path, target)`.
6. On any exception, delete only the temporary file, leave the original unchanged, and raise `ArchiveError("写入失败，原文件已保留：...")`.
7. Never create a backup when new content is byte-for-byte identical.

- [ ] **Step 5: Run focused and full tests**

Run: `uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -v`

Expected: all initialization and atomic-write tests PASS.

Run: `python3 -m py_compile parent-communication-assistant/scripts/manage_profiles.py`

Expected: no output and exit code 0.

- [ ] **Step 6: Commit archive initialization**

```bash
git add parent-communication-assistant/scripts/manage_profiles.py tests
git commit -m "feat: initialize local communication archive"
```

### Task 3: Implement student index, lookup, creation, and promotion

**Files:**
- Modify: `parent-communication-assistant/scripts/manage_profiles.py`
- Modify: `tests/test_manage_profiles.py`

**Interfaces:**
- Consumes: `ArchiveError`, `atomic_write_text()`, `load_settings()` from Task 2.
- Produces: immutable `StudentRecord`, `load_index(data_root)`, `find_students(data_root, name, grade=None, class_name=None)`, `create_student(data_root, name, grade, class_name, confirmed)`, `promote_student(data_root, student_id, grade, class_name, confirmed)`, and `validate_archive(data_root)`.

- [ ] **Step 1: Add failing student lifecycle tests**

```python
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
```

- [ ] **Step 2: Run the student tests and verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -k 'student or create or find or promote or validate' -v`

Expected: FAIL because student lifecycle APIs do not exist.

- [ ] **Step 3: Implement the fixed index model**

Use this exact dataclass:

```python
@dataclass(frozen=True)
class StudentRecord:
    student_id: str
    name: str
    grade: str
    class_name: str
    directory: str
    updated_at: str
```

`load_index()` must parse only the fixed six-column Markdown table. Reject malformed row counts, duplicate IDs, duplicate directory names, unknown ID formats, path separators in fields, and any referenced directory missing during `validate_archive()`.

Validation rules:

```python
STUDENT_ID_RE = re.compile(r"^S\d{4}$")
VALID_GRADES = {"一年级", "二年级", "三年级", "四年级", "五年级", "六年级"}
FORBIDDEN_FIELD_CHARS = {"|", "/", "\\", "\n", "\r"}
```

Generate the next ID from the highest existing numeric suffix plus one. The supported workflow has no delete command, so IDs created through the script are never reused.

- [ ] **Step 4: Implement create and lookup behavior**

`find_students()` performs exact normalized matching: trim surrounding whitespace, require exact name, and optionally filter exact grade and class. It must return all matches rather than guessing.

`create_student()` must:

1. Reject `confirmed=False`.
2. Validate fields.
3. Create `姓名-年级班级`, appending `-Sxxxx` only when the directory name already exists.
4. Create `当前概况.md` with fixed basic-information headings and an empty `沟通记录/` directory.
5. Add a row to `学生索引.md` using today's local date.
6. If any step fails, remove only directories created by this call and leave the prior index unchanged.

- [ ] **Step 5: Implement promotion and archive validation**

`promote_student()` must require confirmation, reject unknown IDs, compute the new visible directory name, preserve the ID suffix when needed for collision avoidance, rename the directory, update the fixed basic-information lines in `当前概况.md`, then update the index. If index writing fails, rename the directory back and restore the old profile from its backup.

`validate_archive()` returns:

```python
{"valid": bool, "errors": list[str], "student_count": int}
```

It must not modify any file.

- [ ] **Step 6: Run all lifecycle tests**

Run: `uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -v`

Expected: PASS.

- [ ] **Step 7: Commit student lifecycle support**

```bash
git add parent-communication-assistant/scripts/manage_profiles.py tests/test_manage_profiles.py
git commit -m "feat: manage student profile lifecycle"
```

### Task 4: Implement confirmed profile and communication writes plus JSON CLI

**Files:**
- Modify: `parent-communication-assistant/scripts/manage_profiles.py`
- Modify: `tests/test_manage_profiles.py`

**Interfaces:**
- Consumes: `StudentRecord`, `load_index()`, `atomic_write_text()`, `validate_archive()`.
- Produces: `write_teacher_profile()`, `write_confirmed_samples()`, `write_current_profile()`, `save_communication()`, `build_parser()`, `main(argv=None)`.
- CLI output: one UTF-8 JSON object on stdout for success; one `{"ok": false, "error": "中文信息"}` object on stderr and a nonzero exit code for expected errors.

- [ ] **Step 1: Add failing confirmed-write tests**

```python
def test_write_current_profile_requires_confirmation(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)

    with pytest.raises(manager.ArchiveError, match="教师确认"):
        manager.write_current_profile(
            data_root, student.student_id, "# 当前概况\n", confirmed=False
        )


def test_save_communication_creates_unique_record_and_updates_date(tmp_path):
    data_root = tmp_path / "archive"
    manager.initialize_archive(data_root, tmp_path / "settings.json")
    student = manager.create_student(data_root, "张三", "三年级", "2班", confirmed=True)
    content = """# 沟通记录

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
"""

    first = manager.save_communication(
        data_root, student.student_id, "2026-08-14", "作业完成问题", content, True
    )
    second = manager.save_communication(
        data_root, student.student_id, "2026-08-14", "作业完成问题", content, True
    )

    assert first.name == "2026-08-14-作业完成问题.md"
    assert second.name == "2026-08-14-作业完成问题-02.md"
    assert manager.find_students(data_root, "张三")[0].updated_at == "2026-08-14"


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
```

- [ ] **Step 2: Run focused tests and verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -k 'write or communication or cli' -v`

Expected: FAIL because confirmed write and CLI functions are missing.

- [ ] **Step 3: Implement confirmed Markdown writes**

All four write functions must reject `confirmed=False` before touching disk.

Required headings:

```python
CURRENT_PROFILE_HEADINGS = (
    "# 当前概况",
    "## 基本信息",
    "## 已确认的长期表现",
    "## 已采取的支持措施",
    "## 家长关注点与沟通偏好",
    "## 尚未解决的问题",
    "## 最近一次沟通结论",
    "## 信息更新时间",
)

COMMUNICATION_HEADINGS = (
    "# 沟通记录",
    "## 已确认事实",
    "## 家长核心关注",
    "## 教师实际回应",
    "## 达成共识",
    "## 待跟进事项",
)

TEACHER_PROFILE_HEADINGS = (
    "# 表达偏好",
    "## 常用称呼",
    "## 回复长度",
    "## 语气与直接程度",
    "## 语气词与表情",
    "## 开场与收尾",
    "## 避免表达",
)
```

Reject content missing any required heading. `write_teacher_profile()` writes only `教师档案/表达偏好.md`. `write_confirmed_samples()` writes only `教师档案/已确认表达样本.md`, requires the title `# 已确认表达样本`, permits at most 10 `## 样本` sections, and rejects additional samples instead of silently truncating them. `write_current_profile()` must verify that the fixed name, grade, and class lines match the selected `StudentRecord`. Sanitize record topics by trimming whitespace, replacing forbidden filename characters `<>:"/\\|?*` with `-`, collapsing repeated dashes, and rejecting an empty result. Validate communication dates with `date.fromisoformat()` and reject non-`YYYY-MM-DD` values.

After writing a communication record, update that student's `最近更新` value in the index to the record date. If the index update fails, delete only the newly created record and leave the old index intact. Never modify `当前概况.md` automatically from a communication record; that is a separate confirmed write.

- [ ] **Step 4: Implement the exact CLI surface**

```text
manage_profiles.py [--settings PATH] init [--data-root PATH]
manage_profiles.py [--settings PATH] validate
manage_profiles.py [--settings PATH] find --name NAME [--grade GRADE] [--class-name CLASS]
manage_profiles.py [--settings PATH] create --name NAME --grade GRADE --class-name CLASS --confirmed
manage_profiles.py [--settings PATH] write-teacher-profile --input-file PATH --confirmed
manage_profiles.py [--settings PATH] write-confirmed-samples --input-file PATH --confirmed
manage_profiles.py [--settings PATH] write-current-profile --student-id ID --input-file PATH --confirmed
manage_profiles.py [--settings PATH] save-communication --student-id ID --date YYYY-MM-DD --topic TOPIC --input-file PATH --confirmed
manage_profiles.py [--settings PATH] promote --student-id ID --grade GRADE --class-name CLASS --confirmed
```

Mutation commands must require the literal `--confirmed` flag. `--input-file` must point to a UTF-8 text file; the script reads it but never deletes it. `init` may create a new archive only at the explicit `--data-root` or the documented default. Every non-init command resolves the archive through the settings file and refuses to continue if validation fails.

- [ ] **Step 5: Run CLI smoke tests in a temporary home**

Run:

```bash
uv run --with pytest --with pyyaml pytest tests/test_manage_profiles.py -v
tmp_dir="$(mktemp -d)"
python3 parent-communication-assistant/scripts/manage_profiles.py \
  --settings "$tmp_dir/settings.json" init --data-root "$tmp_dir/archive"
python3 parent-communication-assistant/scripts/manage_profiles.py \
  --settings "$tmp_dir/settings.json" create \
  --name "张三" --grade "三年级" --class-name "2班" --confirmed
python3 parent-communication-assistant/scripts/manage_profiles.py \
  --settings "$tmp_dir/settings.json" find --name "张三"
```

Expected: pytest passes; all three CLI calls return JSON with `"ok": true`; `find` returns `S0001`.

- [ ] **Step 6: Commit confirmed write operations**

```bash
git add parent-communication-assistant/scripts/manage_profiles.py tests/test_manage_profiles.py
git commit -m "feat: add confirmed archive writes and cli"
```

### Task 5: Add domain references and fixed archive schemas

**Files:**
- Create: `parent-communication-assistant/references/communication-strategies.md`
- Create: `parent-communication-assistant/references/grade-guidance.md`
- Create: `parent-communication-assistant/references/profile-schema.md`
- Create: `parent-communication-assistant/references/risk-boundaries.md`
- Modify: `tests/test_skill_contract.py`

**Interfaces:**
- Produces: 按需加载的领域规则；`SKILL.md` 在 Task 6 通过相对路径直接引用这些文件。
- Contract: 每个 reference 文件只有一个领域职责，不包含 Skill 触发说明，不重复完整主流程。

- [ ] **Step 1: Add failing reference contract tests**

```python
def test_reference_files_cover_required_contracts():
    references = SKILL_DIR / "references"
    strategy = (references / "communication-strategies.md").read_text(encoding="utf-8")
    grades = (references / "grade-guidance.md").read_text(encoding="utf-8")
    schema = (references / "profile-schema.md").read_text(encoding="utf-8")
    risk = (references / "risk-boundaries.md").read_text(encoding="utf-8")

    for action in ["正式回应", "简短确认", "到此结束", "转电话／面谈"]:
        assert action in strategy
    for grade in ["一、二年级", "三、四年级", "五、六年级"]:
        assert grade in grades
    for heading in ["学生索引", "当前概况", "沟通记录", "表达偏好"]:
        assert heading in schema
    for topic in ["受伤", "欺凌", "投诉", "责任认定", "心理诊断"]:
        assert topic in risk
```

- [ ] **Step 2: Run the reference test and verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -k reference -v`

Expected: FAIL because the four reference files are missing.

- [ ] **Step 3: Write communication strategies**

`communication-strategies.md` must contain these sections and exact operational content:

```markdown
# 沟通策略

## 信息分层
- 已确认事实：可直接陈述时间、场景、行为和结果。
- 教师观察：使用“我观察到”“这几次我注意到”等限定表达。
- 主观判断：不得作为事实发送或写入长期档案。

## 四种回复动作
- 正式回应：家长提出具体问题，且教师掌握足够事实。
- 简短确认：家长主要在表达立场或情绪，不需要展开观点辩论。
- 到此结束：事实和下一步行动已经说明，再解释只会重复或升级冲突。
- 转电话／面谈：微信出现连续误解、责任争议、情绪升级或复杂事实核对。

## 微信输出
先给建议动作，再给可直接发送内容，最后各用一句话说明表达策略和避免表达。默认 60～120 字，复杂情况不超过约 180 字。

## 沟通前预案
固定包含核心目标、最低目标、事实与观察、家长关注点、真实正向开场、核心事实、可能异议、短回应、双方行动和结束信号。

## 电话／面谈提纲
按照“30 秒开场→事实→倾听→回应顾虑→双方行动→确认共识→结束”组织，并附 3 个可能异议、短回应、禁止承诺和失控暂停方式。

## 观点争论型家长
承认其关注点，不证明对方观点错误；回到本次具体事项、学校当前安排和下一步行动。事情说清后建议结束。

## 禁止表达
不得虚构表扬、过度道歉、承诺特殊照顾、使用人格标签，或堆砌“底层能力、全面成长、教育的本质”等抽象概念。
```

- [ ] **Step 4: Write grade, schema, and risk references**

`grade-guidance.md` must specify:

- 一、二年级：习惯培养、入学适应、家校协作；避免把偶发行为定性为能力问题。
- 三、四年级：规则意识、学习自主性、同伴关系；说明具体行为和可执行调整。
- 五、六年级：责任感、独立沟通、青春期前后变化；尊重学生参与，不越过学生只与家长定性。
- 所有年级：年龄只调整沟通重点，不用于刻板判断；不作心理诊断。

`profile-schema.md` must include the exact Markdown tables/headings implemented by the script, objective-versus-label examples, teacher voice fields, a maximum of 10 confirmed expression samples, and the rule that raw screenshots and full chats are not persisted by default.

`risk-boundaries.md` must define triggers for injury, bullying, severe discipline, teacher complaints, threats, responsibility attribution, and suspected mental-health concerns. For every trigger require: state confirmed facts only, preserve records, avoid admitting liability or making guarantees, follow school escalation procedures, and prefer formal communication. Explicitly say the Skill does not diagnose, investigate, decide liability, or replace school policy.

- [ ] **Step 5: Run reference contract tests**

Run: `uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -k reference -v`

Expected: PASS.

- [ ] **Step 6: Commit domain references**

```bash
git add parent-communication-assistant/references tests/test_skill_contract.py
git commit -m "docs: add parent communication domain rules"
```

### Task 6: Implement the complete SKILL.md interaction workflow

**Files:**
- Modify: `parent-communication-assistant/SKILL.md`
- Modify: `parent-communication-assistant/agents/openai.yaml`
- Modify: `tests/test_skill_contract.py`

**Interfaces:**
- Consumes: all Task 4 CLI commands and all Task 5 references.
- Produces: a concise Skill workflow that another Codex instance can execute without reading the design document.

- [ ] **Step 1: Add failing workflow contract tests**

```python
def test_skill_requires_progressive_loading_and_confirmation():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    ordered_terms = ["表达偏好.md", "学生索引.md", "当前概况.md", "沟通记录"]
    positions = [text.index(term) for term in ordered_terms]
    assert positions == sorted(positions)
    assert "只有本次问题涉及历史事件" in text
    assert "教师确认" in text
    assert "不得写入" in text
    assert "修复预览" in text


def test_skill_routes_all_four_modes():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for mode in ["沟通前预案", "沟通中陪聊", "电话／面谈", "沟通结束"]:
        assert mode in text


def test_skill_has_reply_decision_protocol():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for label in ["【建议动作】", "【可直接发送】", "【表达策略】", "【避免表达】"]:
        assert label in text
    assert "可以不回复" in text
    assert "只询问一个" in text


def test_skill_routes_references_directly():
    text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    for filename in [
        "references/communication-strategies.md",
        "references/grade-guidance.md",
        "references/profile-schema.md",
        "references/risk-boundaries.md",
    ]:
        assert filename in text
```

- [ ] **Step 2: Run workflow tests and verify failure**

Run: `uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -k 'skill or workflow' -v`

Expected: FAIL because the scaffold body does not contain the complete workflow.

- [ ] **Step 3: Write SKILL.md frontmatter and startup flow**

Use exactly two frontmatter fields:

```yaml
---
name: parent-communication-assistant
description: 为小学一至六年级教师准备家长沟通、生成微信回复或电话面谈提纲，并在教师确认后维护本地教师语气与学生沟通档案。用于教师需要主动联系家长、逐轮回复家长消息、判断是否应结束争论、整理沟通结果、从历史截图学习本人语气，或查询既往学生沟通背景时。
---
```

The body must use imperative Chinese and implement this startup order:

1. Run `validate`; if settings are missing, ask for data-root choice and run `init` only after confirmation.
2. If teacher preference is uninitialized, offer screenshot/text sample analysis or default style; confirm the teacher side before extracting screenshot messages.
3. Read only `表达偏好.md`.
4. Read only `学生索引.md` to match the named student.
5. Resolve duplicates with name, grade, class, and ID.
6. Read the matched `当前概况.md`.
7. Read specific communication records only when the current issue refers to history.

Explicitly prohibit bulk reading of all student folders. If `validate` reports an index or directory mismatch, stop all writes, show the error list and a repair preview, and ask for confirmation before any repair. If an uploaded screenshot is unreadable or speaker ownership is uncertain, ask the teacher to identify their side or paste the key text; never infer missing text.

- [ ] **Step 4: Add the four task modes and reply decision layer**

The Skill body must instruct the agent to:

- route natural language into communication pre-plan, live reply, phone/interview, or completion;
- ask only grade, class, student name, and current problem for a new student, then allow free description;
- show extracted profile content and refuse to call mutation commands before teacher confirmation;
- classify each parent message as concrete question, emotion, refusal, topic shift, or viewpoint debate;
- choose formal response, short acknowledgment, finish/no reply, or phone/interview before drafting words;
- provide a temporary verification message when a critical fact is missing, then ask only one necessary question;
- use the exact four-label output protocol from the test;
- read `risk-boundaries.md` whenever risk triggers appear.

- [ ] **Step 5: Add completion and voice-learning flow**

At communication end, the Skill must ask once whether the teacher directly used or modified the proposed wording. It must:

1. Compare a pasted final version with the suggestion only when supplied.
2. Treat one change as session-specific.
3. After two similar confirmed changes, mention a possible preference.
4. After three similar confirmed changes, propose a precise update.
5. Write `表达偏好.md` or `已确认表达样本.md` only after explicit confirmation.
6. Generate a structured communication summary, show it, and call `save-communication` only after approval.
7. Propose long-term current-profile changes separately and write them only after another explicit approval or a single clearly worded combined approval covering both writes.

- [ ] **Step 6: Regenerate and validate UI metadata**

Run:

```bash
python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/generate_openai_yaml.py \
  parent-communication-assistant \
  --interface 'display_name=家长沟通助手' \
  --interface 'short_description=帮助小学教师准备沟通、生成自然回复并沉淀本地学生档案' \
  --interface 'default_prompt=使用 $parent-communication-assistant 帮我准备并回复这次家长沟通。'
```

Do not add icons, colors, dependencies, or policy fields.

- [ ] **Step 7: Run static tests and the official validator**

Run:

```bash
uv run --with pytest --with pyyaml pytest tests/test_skill_contract.py -v
python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/quick_validate.py parent-communication-assistant
```

Expected: all tests PASS and validator succeeds.

- [ ] **Step 8: Commit the complete workflow**

```bash
git add parent-communication-assistant/SKILL.md parent-communication-assistant/agents/openai.yaml tests/test_skill_contract.py
git commit -m "feat: add parent communication interaction workflow"
```

### Task 7: Add end-to-end fixtures and complete verification

**Files:**
- Create: `tests/fixtures/teacher-style-samples.md`
- Create: `tests/fixtures/difficult-parent-case.md`
- Modify: `tests/test_skill_contract.py`
- Modify: `tests/test_manage_profiles.py`

**Interfaces:**
- Consumes: complete Skill package and archive CLI.
- Produces: repeatable local verification fixtures and a documented pass/fail checklist for the real difficult-parent scenario.

- [ ] **Step 1: Add a failing end-to-end archive test**

```python
def test_end_to_end_confirmed_archive_flow(tmp_path):
    data_root = tmp_path / "archive"
    settings = tmp_path / "settings.json"
    manager.initialize_archive(data_root, settings)
    student = manager.create_student(data_root, "测试学生", "三年级", "2班", True)

    profile = """# 当前概况

## 基本信息
- 姓名：测试学生
- 年级：三年级
- 班级：2班

## 已确认的长期表现
- 暂无长期结论。

## 已采取的支持措施
- 教师在课堂结束前提醒记录作业。

## 家长关注点与沟通偏好
- 不希望额外增加压力；偏好简短、具体表达。

## 尚未解决的问题
- 继续观察作业记录情况。

## 最近一次沟通结论
- 先由教师课堂提醒一周。

## 信息更新时间
- 2026-08-14
"""
    manager.write_current_profile(data_root, student.student_id, profile, True)

    record = """# 沟通记录

## 已确认事实
- 学生当天未记录作业，课后补做约八分钟。

## 家长核心关注
- 不希望小学作业增加压力。

## 教师实际回应
- 说明本次补做用于完成当天任务，不是额外加量。

## 达成共识
- 教师先加强课堂提醒，双方继续观察。

## 待跟进事项
- 一周后复盘记录作业的情况。
"""
    record_path = manager.save_communication(
        data_root, student.student_id, "2026-08-14", "作业完成问题", record, True
    )

    assert manager.validate_archive(data_root)["valid"] is True
    assert record_path.exists()
    assert "偏好简短、具体表达" in (
        data_root / "学生档案" / student.directory / "当前概况.md"
    ).read_text(encoding="utf-8")
```

- [ ] **Step 2: Create the two sanitized fixtures**

`teacher-style-samples.md` must include 8 short teacher messages across praise, homework reminder, behavior feedback, and concern response. Use fictional names and no phone, address, ID number, school name, or real screenshots.

`difficult-parent-case.md` must reproduce this sanitized sequence:

```markdown
# 困难家长场景

## 背景
- 三年级学生当天忘记记录并完成作业，课后约八分钟补完。
- 家长不希望孩子承受学习压力，认为小学知识对未来影响不大。

## 家长消息一
我理想的情况是小学没有课后作业。我知道现在普遍都有，所以也让他补了，但我知道这是不对的。

## 家长消息二
老师，我怎么感觉你说得像 AI 回复的？现在 AI 能代替很多死记硬背的知识，没必要再花太多时间在这些上面。

## 期望决策
- 消息一：简短确认并说明学校当前安排和下一步观察，不展开作业价值辩论。
- 消息二：自然承认上一条过于正式，用短句澄清核心意思并收尾。

## 禁止结果
- 长篇讨论学习的本质、底层能力或全面成长。
- 证明家长教育理念错误。
- 虚构对孩子的表扬。
- 作出取消作业、特殊照顾或学校责任方面的承诺。
```

- [ ] **Step 3: Run the complete automated suite**

Run:

```bash
uv run --with pytest --with pyyaml pytest -v
python3 -m py_compile parent-communication-assistant/scripts/manage_profiles.py
python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/quick_validate.py parent-communication-assistant
git diff --check
```

Expected: all tests PASS, Python compilation succeeds, Skill validation succeeds, and `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Perform a clean forward test of the Skill**

First use a fresh agent context with only the Skill path and `tests/fixtures/teacher-style-samples.md`. Give this exact task:

```text
使用 $parent-communication-assistant 分析 tests/fixtures/teacher-style-samples.md，生成待教师确认的表达偏好画像，并用该语气写一条“学生今天忘记记录作业”的测试消息。不要写入任何真实档案。
```

Check that the output distinguishes source samples from inferred preferences, asks for confirmation before persistence, and produces a short test message rather than a generic essay.

Then use another fresh agent context with only the Skill path and `tests/fixtures/difficult-parent-case.md`. Give this exact task:

```text
使用 $parent-communication-assistant 处理 tests/fixtures/difficult-parent-case.md 中的实时微信沟通。请分别对两条家长消息给出下一步建议和可直接发送的回复。
```

Evaluate the raw output against this checklist:

- each message has `【建议动作】`, `【可直接发送】`, `【表达策略】`, `【避免表达】`;
- the first proposed reply is at most about 180 Chinese visible characters;
- the second suggests natural clarification and closure rather than renewed debate;
- no invented student facts or praise;
- none of “学习的本质、底层能力、全面成长” appears in sendable text;
- no promise to cancel homework, provide special treatment, or accept liability.

If any item fails, revise the smallest relevant part of `SKILL.md` or a reference file, then repeat the same fresh-context test once with no prior output included.

- [ ] **Step 5: Inspect package contents and exclude runtime data**

Run:

```bash
find parent-communication-assistant -maxdepth 3 -type f -print | sort
find parent-communication-assistant -type d -name '__pycache__' -print
git status --short
```

Expected: only `SKILL.md`, `agents/openai.yaml`, the script, and four references are in the Skill package; no student archive, settings file, screenshot, raw chat, `__pycache__`, or backup directory is tracked.

- [ ] **Step 6: Commit fixtures and final verification changes**

```bash
git add tests/fixtures tests/test_manage_profiles.py tests/test_skill_contract.py parent-communication-assistant
git commit -m "test: verify difficult parent communication workflow"
```

## Final Completion Check

Before claiming implementation complete, run:

```bash
uv run --with pytest --with pyyaml pytest -v
python3 -m py_compile parent-communication-assistant/scripts/manage_profiles.py
python3 /Users/kevin/.codex/skills/.system/skill-creator/scripts/quick_validate.py parent-communication-assistant
git status --short
```

Expected:

- all automated tests pass;
- Python compilation and official Skill validation succeed;
- working tree is clean;
- no real student, parent, teacher, screenshot, or chat data appears in tracked files;
- every implementation task has its own commit.
