# Codex Skills

个人维护的 Codex 技能。

## novel-create · 长篇小说创作与续写

从主题、故事世界和人物设定开始，规划总纲与章纲，按章创作正文，并维护续写所需的剧情与人物记录。

- 按需提供主题、世界、人物和大纲模板，以及续写和修订参考。
- 自带活人感写作规则，支持独立使用；创作记录可与 `novel-continuity` 共用。
- 提供项目进度和章节检查脚本，运行脚本需要 Python。

技能入口：[novel-create/SKILL.md](novel-create/SKILL.md)

## novel-continuity · 小说持续创作

中文长篇小说创作、续写与改稿时，读取总纲、分卷纲和已有正文，结合 `human-writing` 维护叙事连续性。

- 同步当前卷已发生总结、紧接章节计划和未发生待办，依据正文逐项核销。
- 维护主要人物的年龄、状态、关系、能力、物品和知情范围。
- 跨卷或新开卷时回读相关上文，对照总纲及前后两卷章纲，检查时间、因果和人物状态的衔接。
- 初稿完成后检查章与场景衔接、对白、心理描写和作者文风；精修已有正文时默认采用局部修改。
- 改稿后撤销失效核销，保留跨卷遗留事项及章节依据。

技能入口：[novel-continuity/SKILL.md](novel-continuity/SKILL.md)

记录格式：[novel-continuity/references/records.md](novel-continuity/references/records.md)

## novel-polish · 小说初稿优化

诊断和润色小说初稿，关注章节、场景和分卷的衔接，以及人物对白与心理描写，同时保留已有剧情、设定和作者文风。

- 支持单段精修、章节衔接检查，以及多章或整卷的分阶段诊断与精修。
- 提供仅诊断、句段精修和场景重写三种修改力度，默认进行句段级精修。
- 按需读取衔接、对白、心理、全书工作流程和连续性档案参考文件。

技能入口：[novel-polish/SKILL.md](novel-polish/SKILL.md)

## 安装

将需要的技能文件夹（`novel-create`、`novel-continuity` 或 `novel-polish`）完整复制到 Codex 技能目录 `$CODEX_HOME/skills/`，未设置 `CODEX_HOME` 时使用 `~/.codex/skills/`。

`novel-continuity` 需要另行安装 `human-writing`（活人感写作）。本仓库未包含该依赖。

## 使用

从头创作时调用：

```text
使用 $novel-create 帮我规划长篇小说的主题、人物和大纲，再写第一章并建立创作记录。
```

在小说项目中调用：

```text
使用 $novel-continuity 读取总纲、当前分卷与已有正文，续写下一章，并同步创作记录和人物状态。
```

已有同用途记录时沿用项目文件；首次建立时默认保存在小说根目录的 `创作记录/`。仅有大纲时，未来事件保留为计划，不能计入已发生事实。

优化已有初稿时调用：

```text
使用 $novel-polish 检查这两章的衔接、对白和心理描写，保留原有剧情和文风，并说明修改原因。
```
