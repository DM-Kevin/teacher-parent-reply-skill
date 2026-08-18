# 教师高情商回复家长 Skill

一个帮助小学教师（尤其三年级）与家长进行高情商沟通的本地 Skill 项目。

## 项目背景

个别家长只愿听夸奖，批评容易被解读为针对，每次沟通都要花半小时查 AI。本 Skill 把高情商沟通沉淀成可复用的方法论与本地档案，让教师「沟通前有预案、沟通中有陪聊、沟通后有总结」。

## 核心功能闭环

- **沟通前预案**：生成完整沟通方案（核心目标、事实与观察、家长关注点、真实开场、核心事实、三个可能异议、双方行动、结束信号）。
- **沟通中陪聊**：逐轮生成可直接发送的回复建议，判断家长是在问事实、表达情绪、拒绝配合还是展开争论。
- **沟通后总结**：整理结构化沟通摘要、更新学生档案，并沉淀教师表达偏好。
- **本地学生档案**：只保存在教师本机，不自动同步或上传，保护真实数据隐私。

## 目录结构

```
parent-communication-assistant/
├── SKILL.md                     # Skill 主指令（家长沟通助手）
├── agents/openai.yaml           # Agent 接口声明
├── references/                  # 领域规则与参考
│   ├── communication-strategies.md  # 沟通策略
│   ├── grade-guidance.md            # 分年级沟通指导
│   ├── profile-schema.md            # 学生档案字段与客观化规则
│   └── risk-boundaries.md           # 高风险场景边界
└── scripts/manage_profiles.py   # 本地档案管理脚本（CLI）
docs/                            # 设计方案与实施计划
tests/                           # 测试与评测
```

## 档案管理脚本

所有写操作都需要字面量 `--confirmed` 才会真正执行：

```text
init --data-root PATH
validate
find --name NAME [--grade GRADE] [--class-name CLASS]
create --name NAME --grade GRADE --class-name CLASS --confirmed
write-teacher-profile --input-file PATH --confirmed
write-confirmed-samples --input-file PATH --confirmed
write-current-profile --student-id ID --input-file PATH --confirmed
save-communication --student-id ID --date YYYY-MM-DD --channel CHANNEL --topic TOPIC --input-file PATH --confirmed
promote --student-id ID --grade GRADE --class-name CLASS --confirmed
```

## 隐私说明

- 真实学生档案保存在教师本机指定的 `家长沟通档案/` 目录，绝不放进 Skill 目录。
- Skill 不做任何自动同步或上传；临时载荷文件用后即删。
- 档案写入遵循「先预览、再确认、才落盘」的原则。

## 开发

```bash
python3 parent-communication-assistant/scripts/manage_profiles.py --help
python3 -m pytest tests/
```
