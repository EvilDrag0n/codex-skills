# Codex Skills

个人维护的 Codex 技能。

## novel-continuity · 小说持续创作

中文长篇小说创作、续写与改稿时，读取总纲、分卷纲和已有正文，结合 `human-writing` 维护叙事连续性。

- 同步当前卷已发生总结、紧接章节计划和未发生待办，依据正文逐项核销。
- 维护主要人物的年龄、状态、关系、能力、物品和知情范围。
- 跨卷或新开卷时回读相关上文，对照总纲及前后两卷章纲，检查时间、因果和人物状态的衔接。
- 改稿后撤销失效核销，保留跨卷遗留事项及章节依据。

技能入口：[novel-continuity/SKILL.md](novel-continuity/SKILL.md)

记录格式：[novel-continuity/references/records.md](novel-continuity/references/records.md)

## 安装

将本仓库的 `novel-continuity` 文件夹复制到 Codex 技能目录 `$CODEX_HOME/skills/`，未设置 `CODEX_HOME` 时使用 `~/.codex/skills/`。

此技能需要另行安装 `human-writing`（活人感写作）。本仓库未包含该依赖。

## 使用

在小说项目中调用：

```text
使用 $novel-continuity 读取总纲、当前分卷与已有正文，续写下一章，并同步创作记录和人物状态。
```

已有同用途记录时沿用项目文件；首次建立时默认保存在小说根目录的 `创作记录/`。仅有大纲时，未来事件保留为计划，不能计入已发生事实。
