#!/usr/bin/env python3
"""列出小说项目的现状，帮助续写前恢复进度。只读，不改任何文件。

用法
    python novel_status.py [小说根目录] [--json]

输出现有的设定和大纲文件、章节数与字数、最新章节、缺号和重号、
创作记录各自同步到哪一章，以及建议先读哪些文件。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

NUMERAL = r"[0-9０-９零〇一二两三四五六七八九十百千]+"
CHAPTER_RE = re.compile(rf"第\s*({NUMERAL})\s*章")
VOLUME_RE = re.compile(rf"第\s*({NUMERAL})\s*卷")
HEADING_RE = re.compile(rf"^[ \t　]*#*[ \t　]*第\s*({NUMERAL})\s*章[^\n]*$", re.MULTILINE)
VOLUME_HEADING_RE = re.compile(rf"^[ \t　]*#*[ \t　]*第\s*({NUMERAL})\s*卷", re.MULTILINE)
SYNC_RE = re.compile(r"同步至[^\n]*")
OUTLINE_ROW_RE = re.compile(r"^[ \t]*\|[ \t]*(?:第[ \t]*)?(\d{1,4})[ \t]*章?[ \t]*\|", re.MULTILINE)
PROGRESS_RECORDS = ("已发生总结", "紧接章节计划", "未发生待办", "角色记录", "人物状态")

TEXT_SUFFIXES = {".md", ".txt", ".markdown"}
RECORD_DIR_NAMES = {"创作记录"}
NON_BODY_DIRS = {
    "创作记录", "大纲", "设定", "草稿", "废弃", "存档", "备份", "素材", "参考",
    ".git", ".obsidian", "node_modules", "assets", "references", "scripts",
}
OUTLINE_WORDS = ("章纲", "细纲", "大纲", "总纲")
NON_BODY_WORDS = OUTLINE_WORDS + ("计划", "总结", "待办", "设定", "记录", "说明", "技巧", "指南")
STATUS_WORDS = ("未开始", "进行中", "已完成", "延期", "取消")

KEY_DOCS = (
    ("项目说明", ("项目说明", "README", "readme")),
    ("主题与卖点", ("主题", "立意", "卖点")),
    ("故事世界", ("世界", "背景设定", "设定集", "力量体系")),
    ("人物设定", ("人物设定", "人物小传", "角色设定", "人设")),
    ("全书总纲", ("总纲", "全书大纲", "故事大纲")),
    ("章纲", ("章纲", "细纲", "分卷")),
)

CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def to_int(value: str) -> int:
    """把阿拉伯数字、全角数字或中文数字转成整数。"""

    value = value.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if value.isdigit():
        return int(value)
    if all(char in CN_DIGITS for char in value):
        return int("".join(str(CN_DIGITS[char]) for char in value))
    total, current = 0, 0
    for char in value:
        if char in CN_DIGITS:
            current = CN_DIGITS[char]
        elif char in CN_UNITS:
            total += (current or 1) * CN_UNITS[char]
            current = 0
    return total + current


def han_count(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def body_han(text: str) -> int:
    """正文字数。不算文件头元数据、标题行和章节标题行，和 check_chapter.py 的口径一致。"""

    text = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", "", text, flags=re.DOTALL)
    text = re.sub(r"^[ \t]*#{1,6}[ \t].*$", "", text, flags=re.MULTILINE)
    text = re.sub(rf"^[ \t　]*第{NUMERAL}[章卷回节][^\n]{{0,40}}$", "", text, flags=re.MULTILINE)
    return han_count(text)


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


@dataclass
class Chapter:
    volume: int
    number: int
    title: str
    path: str
    words: int
    line: int = 0


def volume_of(parts: tuple[str, ...]) -> int:
    for part in reversed(parts):
        match = VOLUME_RE.search(part)
        if match:
            return to_int(match.group(1))
    return 0


def text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
            yield path


def is_body_candidate(root: Path, path: Path, words: tuple[str, ...]) -> bool:
    relative = path.relative_to(root)
    if any(part in NON_BODY_DIRS for part in relative.parts[:-1]):
        return False
    return not any(word in path.stem for word in words)


def collect_chapters(root: Path) -> tuple[list[Chapter], str]:
    """先找一章一个文件的布局，找不到再找整本放在一个文件里的布局。"""

    chapters: list[Chapter] = []
    for path in text_files(root):
        # 章节标题里可能有“计划”“记录”这类词，这里只排除明确是大纲的文件。
        if not is_body_candidate(root, path, OUTLINE_WORDS):
            continue
        match = CHAPTER_RE.search(path.stem)
        if not match:
            continue
        relative = path.relative_to(root)
        chapters.append(
            Chapter(
                volume=volume_of(relative.parts),
                number=to_int(match.group(1)),
                title=path.stem,
                path=relative.as_posix(),
                words=body_han(read_text(path)),
            )
        )
    if chapters:
        return chapters, "一章一个文件"

    for path in text_files(root):
        if not is_body_candidate(root, path, NON_BODY_WORDS):
            continue
        text = read_text(path)
        headings = list(HEADING_RE.finditer(text))
        if len(headings) < 2:
            continue
        relative = path.relative_to(root)
        current_volume = volume_of(relative.parts)
        volume_marks = [
            (mark.start(), to_int(mark.group(1))) for mark in VOLUME_HEADING_RE.finditer(text)
        ]
        mark_index = 0
        volume = current_volume
        for index, heading in enumerate(headings):
            end = headings[index + 1].start() if index + 1 < len(headings) else len(text)
            while mark_index < len(volume_marks) and volume_marks[mark_index][0] < heading.start():
                volume = volume_marks[mark_index][1]
                mark_index += 1
            chapters.append(
                Chapter(
                    volume=volume,
                    number=to_int(heading.group(1)),
                    title=heading.group().strip(" \t　#"),
                    path=relative.as_posix(),
                    words=body_han(text[heading.end() : end]),
                    line=text.count("\n", 0, heading.start()) + 1,
                )
            )
    return chapters, "整本在一个文件里" if chapters else "未找到正文"


def find_key_docs(root: Path, body_paths: set[str]) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {label: [] for label, _ in KEY_DOCS}
    for path in text_files(root):
        relative = path.relative_to(root)
        parts = relative.parts
        if relative.as_posix() in body_paths:
            continue
        if any(
            part in RECORD_DIR_NAMES or part in {"存档", "废弃", "备份", "草稿", "assets", "references", "scripts"}
            for part in parts[:-1]
        ):
            continue
        if CHAPTER_RE.search(path.stem) and not any(word in path.stem for word in OUTLINE_WORDS):
            continue
        for label, words in KEY_DOCS:
            if any(word in path.stem for word in words):
                found[label].append(relative.as_posix())
                break
    return found


def parse_sync(text: str) -> tuple[int, int] | None:
    """读记录头部的“同步至”，返回（卷，章）。没写章号时返回 None。"""

    for match in SYNC_RE.finditer(text):
        line = match.group()
        chapter = CHAPTER_RE.search(line)
        if not chapter:
            continue
        volume = VOLUME_RE.search(line)
        return (to_int(volume.group(1)) if volume else 0, to_int(chapter.group(1)))
    return None


def collect_records(root: Path) -> list[dict]:
    records = []
    skip = {"assets", "templates", "references", "scripts", "存档", "废弃", "备份"}
    for directory in sorted(path for path in root.rglob("*") if path.is_dir() and path.name in RECORD_DIR_NAMES):
        if any(part in skip for part in directory.relative_to(root).parts):
            continue
        for path in sorted(directory.rglob("*.md")):
            text = read_text(path)
            relative = path.relative_to(root)
            entry = {
                "path": relative.as_posix(),
                "volume": volume_of(relative.parts),
                "sync": parse_sync(text),
                "not_started": "正文尚未开始" in text,
            }
            if "待办" in path.stem:
                counts = {word: 0 for word in STATUS_WORDS}
                for row in text.splitlines():
                    if not row.strip().startswith("|"):
                        continue
                    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
                    for word in STATUS_WORDS:
                        if word in cells:
                            counts[word] += 1
                entry["todo"] = counts
            records.append(entry)
    return records


def numbering_issues(chapters: list[Chapter]) -> tuple[list[str], list[str]]:
    gaps, duplicates = [], []
    by_volume: dict[int, list[int]] = {}
    for chapter in chapters:
        by_volume.setdefault(chapter.volume, []).append(chapter.number)
    for volume, numbers in sorted(by_volume.items()):
        label = f"第{volume}卷" if volume else "全书"
        seen = set()
        for number in numbers:
            if number in seen:
                duplicates.append(f"{label}第{number}章")
            seen.add(number)
        missing = [number for number in range(min(numbers), max(numbers) + 1) if number not in seen]
        if missing:
            shown = "、".join(str(number) for number in missing[:12])
            gaps.append(f"{label}缺第 {shown} 章" + ("等" if len(missing) > 12 else ""))
    return gaps, duplicates


def label_of(volume: int, number: int) -> str:
    return f"第{volume}卷 第{number:03d}章" if volume else f"第{number:03d}章"


def build_report(root: Path) -> dict:
    chapters, layout = collect_chapters(root)
    chapters.sort(key=lambda chapter: (chapter.volume, chapter.number))
    docs = find_key_docs(root, {chapter.path for chapter in chapters})
    records = collect_records(root)
    gaps, duplicates = numbering_issues(chapters) if chapters else ([], [])
    latest = chapters[-1] if chapters else None

    stale = []
    for record in records:
        if not any(word in Path(record["path"]).stem for word in PROGRESS_RECORDS):
            record["state"] = "不随章节同步"
            continue
        if latest is None:
            continue
        if record["volume"] and latest.volume and record["volume"] < latest.volume:
            record["state"] = "历史卷"
            continue
        sync = record["sync"]
        if sync is None:
            record["state"] = "落后" if record["not_started"] else "未标同步进度"
            stale.append(record["path"])
            continue
        if latest.volume:
            # 正文分了卷。记录没写卷号时，按它所在的卷目录或最新一卷算。
            behind = (sync[0] or record["volume"] or latest.volume, sync[1]) < (latest.volume, latest.number)
        else:
            # 正文没分卷，只比章号。
            behind = sync[1] < latest.number
        if behind:
            record["state"] = "落后"
            stale.append(record["path"])
        else:
            record["state"] = "已同步"

    volumes: dict[int, dict] = {}
    for chapter in chapters:
        entry = volumes.setdefault(chapter.volume, {"chapters": 0, "words": 0})
        entry["chapters"] += 1
        entry["words"] += chapter.words

    missing_docs = [label for label, paths in docs.items() if not paths]
    if not chapters:
        order = ["主题与卖点", "人物设定", "故事世界", "全书总纲", "章纲"]
        first_missing = next((label for label in order if label in missing_docs), None)
        if first_missing:
            next_step = f"还没有正文。下一步做“{first_missing}”。"
        else:
            next_step = "设定和大纲齐了，可以写第一章。"
    elif stale:
        next_step = "记录落后于正文。先把落后的记录补到最新一章，再续写。"
    else:
        next_step = f"接着 {label_of(latest.volume, latest.number)} 往下写。"

    # 当前卷的章纲，以及它细化到了哪一章
    chapter_outlines = docs["章纲"]
    if latest is not None and latest.volume:
        # 文件名里的卷号可能是阿拉伯数字也可能是中文数字。
        current = [
            item
            for item in chapter_outlines
            if any(to_int(mark.group(1)) == latest.volume for mark in VOLUME_RE.finditer(item))
        ]
        chapter_outlines = current or chapter_outlines
    outlined_to = 0
    for item in chapter_outlines:
        numbers = [int(match.group(1)) for match in OUTLINE_ROW_RE.finditer(read_text(root / item))]
        outlined_to = max([outlined_to, *numbers])
    if latest is not None and not stale and outlined_to and latest.number >= outlined_to:
        next_step = (
            f"章纲只细化到第{outlined_to:03d}章，正文已经写到 {label_of(latest.volume, latest.number)}。"
            "先补后面的章纲，或者开新卷，再续写。"
        )

    reading = []
    if chapters:
        for label in ("项目说明", "全书总纲"):
            reading.extend(docs[label][:2])
        reading.extend(chapter_outlines[:2])
        current_records = [
            record["path"] for record in records if record.get("state") != "历史卷"
        ]
        if latest.volume:
            # 跨卷的记录排在前面，当前卷的三份跟在后面。
            current_records.sort(key=lambda item: (f"第{latest.volume}卷" in item, item))
        reading.extend(current_records)
        reading.append(f"{latest.path}（上一章全文" + (f"，从第 {latest.line} 行起）" if latest.line else "）"))

    return {
        "root": str(root),
        "layout": layout,
        "docs": docs,
        "missing_docs": missing_docs,
        "total_chapters": len(chapters),
        "total_words": sum(chapter.words for chapter in chapters),
        "volumes": {str(volume): data for volume, data in sorted(volumes.items())},
        "latest": latest.__dict__ if latest else None,
        "recent": [chapter.__dict__ for chapter in chapters[-3:]],
        "gaps": gaps,
        "duplicates": duplicates,
        "records": records,
        "stale_records": stale,
        "outlined_to": outlined_to,
        "next_step": next_step,
        "reading_order": reading,
    }


def print_report(report: dict) -> None:
    print(f"小说根目录  {report['root']}")
    print(f"正文布局    {report['layout']}")

    print("\n设定与大纲")
    for label, paths in report["docs"].items():
        shown = "、".join(paths[:3]) + (f" 等 {len(paths)} 个" if len(paths) > 3 else "")
        print(f"  {label}  " + (shown if paths else "缺"))
    if report["outlined_to"]:
        print(f"  章纲细化到第{report['outlined_to']:03d}章")
    elif report["docs"]["章纲"]:
        print("  章纲文件里没认出章纲表。表格第一栏只写章号的数字才认得出")

    print("\n正文")
    if report["total_chapters"]:
        print(f"  共 {report['total_chapters']} 章，{report['total_words']} 字")
        for volume, data in report["volumes"].items():
            name = f"第{volume}卷" if volume != "0" else "未分卷"
            average = data["words"] // data["chapters"] if data["chapters"] else 0
            print(f"  {name}  {data['chapters']} 章，{data['words']} 字，章均 {average} 字")
        print("  最近的章节")
        for chapter in report["recent"]:
            print(f"    {label_of(chapter['volume'], chapter['number'])}  {chapter['words']} 字  {chapter['path']}")
        for item in report["gaps"]:
            print(f"  缺号  {item}")
        for item in report["duplicates"]:
            print(f"  重号  {item}")
    else:
        print("  还没有正文")

    print("\n创作记录")
    if report["records"]:
        for record in report["records"]:
            if record.get("state") == "不随章节同步":
                print(f"  不随章节同步  {record['path']}")
                continue
            if record["sync"]:
                sync = label_of(record["sync"][0] or record["volume"], record["sync"][1])
            elif record["not_started"]:
                sync = "正文尚未开始"
            else:
                sync = "未标"
            line = f"  {record.get('state', '无正文可比')}  同步至 {sync}  {record['path']}"
            print(line)
            if "todo" in record:
                counts = "，".join(f"{word} {count}" for word, count in record["todo"].items() if count)
                print(f"        待办 {counts or '无条目'}")
    else:
        print("  没有创作记录")

    print(f"\n下一步  {report['next_step']}")
    if report["reading_order"]:
        print("\n续写前先读")
        for index, item in enumerate(report["reading_order"], 1):
            print(f"  {index}. {item}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="列出小说项目的现状，帮助续写前恢复进度")
    parser.add_argument("root", nargs="?", default=".", help="小说根目录，默认当前目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"找不到目录 {root}", file=sys.stderr)
        return 2

    report = build_report(root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
