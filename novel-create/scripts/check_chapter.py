#!/usr/bin/env python3
"""检查小说章节的硬禁令、模型套语和网文常见毛病。只报警，不改文。

用法
    python check_chapter.py 章节.md [更多章节 ...] [--target 3000] [--tolerance 0.15]

叙述里的硬禁令判为“需要修改”，退出码为 1。其余列为“需要人工判断”。
规则说明见 references/living-prose.md 和 references/revision.md。
"""

from __future__ import annotations

import argparse
import collections
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 硬禁令

HARD_STOPS = ("说白了", "说穿了", "先说结论")

ROAD_SIGNS = (
    "更微妙的是",
    "值得注意的是",
    "需要指出的是",
    "从某种意义上说",
    "总而言之",
    "综上所述",
)

HARD_JARGON = (
    "赋能", "抓手", "商业闭环", "价值闭环", "能力沉淀", "拉通", "底层逻辑",
    "顶层设计", "认知跃迁", "价值释放", "降本增效", "内容矩阵", "全链路",
    "组合拳", "深层逻辑", "认知增量", "迭代闭环",
)

PIVOT_PATTERNS = (
    re.compile(r"(?:并)?不是[^。！？\n]{0,60}而是"),
    re.compile(r"不(?:仅仅|仅|单)是[^。！？\n]{0,60}而是"),
    re.compile(r"并非[^。！？\n]{0,60}而是"),
    re.compile(r"不在于[^。！？\n]{0,60}而在于"),
    re.compile(r"与其说[^。！？\n]{0,60}(?:不如|毋宁|倒不如)"),
    re.compile(r"[。！？]\s*而是"),
    re.compile(r"表面(?:上)?[^。！？\n]{0,60}(?:其实|实际|实则)"),
    re.compile(r"看似[^。！？\n]{0,60}(?:其实|实际|实则)"),
)

SOFT_PIVOT_PATTERNS = (
    re.compile(r"(?:总|一直|曾|都)以为[^！？\n]{2,50}?(?:其实|才发现|才明白|才知道|后来才)"),
    re.compile(r"(?:并)?不是[^。！？\n]{1,30}，(?:更|才)?是[^，。！？\n]"),
    re.compile(r"[^，。！？\n]{1,12}不重要，(?:重要|要紧)的是"),
    re.compile(r"真正[^，。！？\n]{0,16}的(?:，)?是"),
    re.compile(r"恰恰相反"),
)

DASHES = re.compile(r"[—–─―]+")
COLONS = re.compile(r"[：:]")
OPEN_QUOTES = ("“", "「", "『", "‘", '"')

# ---------------------------------------------------------------- 提醒项

CLICHES = {
    "表情": (
        r"嘴角[^，。！？\n]{0,6}(?:勾起|扬起|上扬|噙着|泛起)",
        r"一抹[^，。！？\n]{0,8}(?:弧度|笑意|冷笑|微笑|苦笑|笑容)",
        r"眼(?:中|里|底|神中)[^，。！？\n]{0,4}(?:闪过|掠过|划过|浮现)",
        r"瞳孔[^，。！？\n]{0,4}(?:骤缩|一缩|收缩|放大)",
        r"眉头(?:微蹙|紧锁|一皱|微皱)",
        r"眸(?:光|色)[^，。！？\n]{0,4}(?:一沉|一暗|微动|深了)",
    ),
    "身体反应": (
        r"深吸(?:了)?一口气",
        r"倒吸(?:了)?一口(?:凉|冷)气",
        r"心(?:头|中|里)(?:一震|一凛|一紧|一沉|一颤|咯噔)",
        r"浑身一(?:震|僵|颤)",
        r"指(?:节|尖|关节)[^，。！？\n]{0,4}(?:泛白|发白)",
        r"喉结[^，。！？\n]{0,4}滚动",
        r"呼吸(?:一滞|一窒|都停了)",
        r"指甲[^，。！？\n]{0,6}(?:嵌|陷|掐)进",
    ),
    "气氛": (
        r"空气(?:仿佛|似乎|好像|像是)?[^，。！？\n]{0,4}(?:凝固|凝滞|静止)",
        r"时间(?:仿佛|似乎|好像|像是)[^，。！？\n]{0,4}(?:静止|停滞|凝固)",
        r"气氛[^，。！？\n]{0,6}冰点",
        r"死一般的?(?:寂静|沉寂)",
        r"落针可闻",
    ),
    "抽象情绪": (
        r"五味杂陈",
        r"说不清(?:，)?道不明",
        r"莫名的[^，。！？\n]{0,6}(?:情绪|感觉|滋味)",
        r"难以言(?:喻|说|表)",
        r"一股暖流",
        r"涌上心头",
        r"(?:神情|神色|眼神|目光|表情)复杂",
        r"百感交集",
    ),
    "叙述腔": (
        r"(?:这|那)一刻[，,]?(?:他|她|他们)?(?:终于|才|忽然)?(?:明白|知道|意识到|懂)",
        r"不知道的是",
        r"殊不知",
        r"命运的(?:齿轮|安排|玩笑)",
        r"一切[^，。！？\n]{0,4}才刚刚开始",
        r"从今往后|从此以后",
        r"注定[^，。！？\n]{0,10}不(?:平凡|平静|寻常)",
    ),
    "声音": (
        r"富有磁性",
        r"不容置(?:疑|喙)",
        r"一字一顿",
        r"声音不大[，,]?却",
    ),
}

APPEARANCE_TERMS = (
    "肤如凝脂", "吹弹可破", "倾国倾城", "闭月羞花", "沉鱼落雁", "国色天香",
    "琼鼻", "樱唇", "樱桃小嘴", "柳眉", "黛眉", "秋水", "星眸", "杏眸", "美眸",
    "明眸皓齿", "贝齿", "青丝", "三千青丝", "盈盈一握", "不食人间烟火", "谪仙",
    "剑眉", "星目", "面如冠玉", "丰神俊朗", "刀削般", "棱角分明", "薄唇",
    "桃花眼", "丹凤眼", "俊美绝伦", "俊美无俦", "玉树临风", "芝兰玉树",
    "白衣胜雪", "冰肌玉骨", "眉如远山", "眉目如画", "顾盼生辉", "身姿挺拔",
    "凹凸有致", "玲珑有致", "曼妙", "娇躯", "酥胸", "玉颈", "香肩", "惊心动魄",
)

EMPTY_ACTIONS = re.compile(
    r"点了点头|点点头|摇了摇头|摇摇头|耸了耸肩|耸耸肩|笑了笑|叹了口气|叹了一口气"
    r"|皱了皱眉|皱起眉头|皱起了眉|愣了一下|愣了愣|怔了一下|怔了怔|顿了顿|顿了一下"
    r"|看了(?:他|她|它|对方)一眼|沉默了(?:片刻|一会儿|几秒)|微微一笑|微微一愣|微微颔首"
)

EMOTION_LABELS = re.compile(
    r"(?:感到|感觉到|觉得)(?:了)?(?:一阵|一丝|一股|一种|无比|十分|非常)"
    r"|心(?:中|里|头|底)(?:涌起|升起|泛起|生出|闪过|充满)"
    r"|不由得|不由自主|忍不住|情不自禁"
)

HEDGES = re.compile(r"似乎|仿佛|好像|宛如|犹如|宛若|某种|一丝|一抹|一股")

SUDDEN = re.compile(r"突然|忽然|猛地|猛然|就在这时|就在此时|没想到|下一秒|刹那间|霎时间|蓦地")

TAG_ADVERBS = re.compile(
    r"(?:冷冷|淡淡|缓缓|轻轻|幽幽|沉声|低声|厉声|冷声|柔声|沉沉|慢慢)(?:地)?"
    r"(?:说道|说|道|开口|问道|问|回答|答道|笑道)"
)

ENDING_PATTERNS = (
    re.compile(r"不知道的是|殊不知|尚不知道|还不知道"),
    re.compile(r"才刚刚开始|刚刚拉开(?:序幕|帷幕)|拉开了(?:序幕|帷幕)"),
    re.compile(r"命运|宿命|时代|未来的路|新的篇章|新的征程"),
    re.compile(r"(?:他|她|他们)(?:知道|明白|清楚)[，,][^。！？\n]{4,}"),
    re.compile(r"(?:风暴|暗流|阴谋|危机)[^。！？\n]{0,10}(?:酝酿|逼近|涌动|等着|来临|降临)"),
    re.compile(r"从(?:此|今往后|这一刻起)"),
)

SETTING_MARKERS = (
    "分为", "共有", "共分", "境界", "等级", "相传", "据说", "传说中", "千年前",
    "万年前", "大陆", "帝国", "王朝", "宗门", "种族", "势力", "体系", "之一",
    "依次是", "分别是", "由低到高", "从低到高",
)

ABSTRACT_LYRIC = re.compile(
    r"(?:时间|岁月|时光|光阴|命运|沉默|孤独|寂寞|记忆|回忆|往事|悲伤|绝望|思念|过去|青春)"
    r"[^，。！？\n]{0,8}?"
    r"(?:保管|磨平|冲淡|冲刷|吞没|吞噬|淹没|发芽|生根|流淌|爬上|爬满|啃噬|蔓延|缠绕|沉淀|打磨|雕刻|封存|带走了|教会了)"
)

NOMINALIZATION_PATTERNS = (
    re.compile(r"进行(?:了|一次|一场|着)?[^。，！？\n]{0,8}(?:调整|分析|讨论|沟通|探索|尝试|思考|观察|检查)"),
    re.compile(r"完成了?对[^。，！？\n]{0,12}的"),
    re.compile(r"起到了?[^。，！？\n]{0,10}的?作用"),
)

CONJUNCTIONS = ("因为", "所以", "但是", "然而", "同时", "此外", "而且", "并且", "因此", "于是")

QUOTED = re.compile(r"“[^”\n]*(?:”|$)|「[^」\n]*(?:」|$)|『[^』\n]*(?:』|$)|\"[^\"\n]*\"", re.MULTILINE)
BRACKETED = re.compile(r"【[^】\n]*】")
SENTENCE = re.compile(r"[^。！？!?\n]+[。！？!?…]+")

# ---------------------------------------------------------------- 工具


def han_count(text: str) -> int:
    return len(re.findall(r"[一-鿿]", text))


def line_no(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def excerpt(value: str, width: int = 40) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    return value if len(value) <= width else value[: width - 1] + "…"


def blank(match: re.Match[str]) -> str:
    return "".join("\n" if char == "\n" else "　" for char in match.group())


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def mask_non_prose(text: str) -> str:
    """屏蔽不属于小说行文的部分，保留字符位置。

    包括文件头元数据、代码块、标题行、引用块和【】里的文内文本。
    """

    masked = re.sub(r"\A---\s*\n.*?\n---\s*(?:\n|\Z)", blank, text, flags=re.DOTALL)
    masked = re.sub(r"```.*?```", blank, masked, flags=re.DOTALL)
    masked = re.sub(r"^[ \t]*#{1,6}[ \t].*$", blank, masked, flags=re.MULTILINE)
    masked = re.sub(r"^[ \t]*>.*$", blank, masked, flags=re.MULTILINE)
    masked = re.sub(
        r"^[ \t　]*第[0-9０-９零〇一二两三四五六七八九十百千]+[章卷回节][^\n]{0,40}$",
        blank,
        masked,
        flags=re.MULTILINE,
    )
    masked = BRACKETED.sub(blank, masked)
    return masked


def split_voice(prose: str) -> tuple[str, str]:
    """返回（只剩叙述的文本，只剩对白的文本），位置与原文一致。"""

    narration = QUOTED.sub(blank, prose)
    dialogue_chars = list("\n" if char == "\n" else "　" for char in prose)
    for match in QUOTED.finditer(prose):
        for index in range(match.start(), match.end()):
            dialogue_chars[index] = prose[index]
    return narration, "".join(dialogue_chars)


def paragraphs_of(text: str) -> list[tuple[int, str]]:
    result = []
    for match in re.finditer(r"[^\n]+", text):
        value = match.group().strip(" \t　")
        if han_count(value) >= 1:
            result.append((match.start(), value))
    return result


def per_thousand(count: int, total: int) -> float:
    return count * 1000 / total if total else 0.0


def anaphora_runs(text: str, minimum: int = 3):
    hits = []
    for sentence in re.finditer(r"[^。！？!?\n]+(?:[。！？!?]|$)", text):
        clauses = [
            clause.strip(" 　")
            for clause in re.split(r"[，、；,;]", sentence.group())
            if han_count(clause) >= 3
        ]
        if len(clauses) < minimum:
            continue
        run = 1
        for previous, current in zip(clauses, clauses[1:]):
            # 以人称代词起头的小句只比第一个字，“他来了，他看见了，他走了”也算同构。
            width = 1 if current[:1] in "他她我它你" else 2
            if previous[:width] == current[:width] and re.match(r"[一-鿿]{%d}" % width, current):
                run += 1
                if run >= minimum:
                    hits.append(sentence)
                    break
            else:
                run = 1
    return hits


def sentence_cv(text: str):
    lengths = [han_count(m.group()) for m in SENTENCE.finditer(text) if han_count(m.group()) >= 4]
    if len(lengths) < 15:
        return None
    mean = sum(lengths) / len(lengths)
    variance = sum((value - mean) ** 2 for value in lengths) / len(lengths)
    return (variance ** 0.5) / mean, len(lengths)


# ---------------------------------------------------------------- 检查


def check(path: Path, target: int | None, tolerance: float) -> tuple[list[str], list[str], dict]:
    text = read_text(path)
    prose = mask_non_prose(text)
    narration, dialogue = split_voice(prose)

    total = han_count(prose)
    narration_han = han_count(narration)
    dialogue_han = han_count(dialogue)
    failures: list[str] = []
    warnings: list[str] = []
    stats = {"汉字数": total, "对白占比": (dialogue_han / total) if total else 0.0}

    if total == 0:
        failures.append("没有检测到小说正文。")
        return failures, warnings, stats

    # 破折号，叙述和对白都算
    dashes = list(DASHES.finditer(prose))
    if dashes:
        lines = "、".join(dict.fromkeys(str(line_no(text, m.start())) for m in dashes[:10]))
        failures.append(
            f"破折号共 {len(dashes)} 处，第 {lines} 行。话被打断用省略号，或者让动作直接切进来。"
        )

    # 冒号，只允许引出原话
    bad_colons = []
    for match in COLONS.finditer(prose):
        before = prose[match.start() - 1 : match.start()]
        after = prose[match.end() : match.end() + 1]
        if before.isdigit() and after.isdigit():
            continue
        if prose[match.end() : match.end() + 3].lstrip(" 　")[:1] in OPEN_QUOTES:
            continue
        bad_colons.append(match)
    if bad_colons:
        lines = "、".join(dict.fromkeys(str(line_no(text, m.start())) for m in bad_colons[:10]))
        failures.append(
            f"提示性冒号共 {len(bad_colons)} 处，第 {lines} 行。冒号只用来引出人物原话，"
            "面板、书信、告示放进引用块或【】里。"
        )

    # 翻案句，叙述里判失败，对白里只提醒
    for pattern in PIVOT_PATTERNS:
        for match in pattern.finditer(narration):
            failures.append(
                f"叙述里的翻案句，第 {line_no(text, match.start())} 行，“{excerpt(match.group())}”。从正面下判断。"
            )
    dialogue_pivots = [m for pattern in PIVOT_PATTERNS for m in pattern.finditer(dialogue)]
    if dialogue_pivots:
        lines = "、".join(dict.fromkeys(str(line_no(text, m.start())) for m in dialogue_pivots[:8]))
        warnings.append(
            f"对白里的翻案句式 {len(dialogue_pivots)} 处，第 {lines} 行。"
            "是这个人物的说话习惯就留，好几个人都这么说就改。"
        )
    soft = [m for pattern in SOFT_PIVOT_PATTERNS for m in pattern.finditer(narration)]
    for match in sorted(soft, key=lambda m: m.start())[:5]:
        warnings.append(
            f"疑似翻案腔，第 {line_no(text, match.start())} 行，“{excerpt(match.group())}”。"
            "先立误解再推翻就改，正常用法保留。"
        )

    # 硬停词、路标、黑话，只查叙述
    for label, terms in (("硬停词", HARD_STOPS), ("模型路标", ROAD_SIGNS), ("商业黑话", HARD_JARGON)):
        for term in terms:
            for match in re.finditer(re.escape(term), narration):
                failures.append(f"{label}，第 {line_no(text, match.start())} 行，{term}")

    # 模型套语
    cliche_hits = collections.Counter()
    cliche_lines: dict[str, list[int]] = collections.defaultdict(list)
    by_category = collections.Counter()
    for category, patterns in CLICHES.items():
        for pattern in patterns:
            for match in re.finditer(pattern, narration):
                key = excerpt(match.group(), 14)
                cliche_hits[key] += 1
                cliche_lines[key].append(line_no(text, match.start()))
                by_category[category] += 1
    cliche_total = sum(cliche_hits.values())
    stats["套语"] = cliche_total
    crowded = [category for category, count in by_category.items() if count >= 3]
    if crowded or per_thousand(cliche_total, total) > 3:
        samples = "、".join(
            f"{phrase}（第 {'、'.join(map(str, cliche_lines[phrase][:3]))} 行）"
            for phrase, _ in cliche_hits.most_common(6)
        )
        detail = "、".join(f"{category} {by_category[category]} 处" for category in by_category)
        warnings.append(
            f"模型套语共 {cliche_total} 处，{detail}。出现最多的有{samples}。"
            "同一类三次以上的，回到人物此刻的处境里重写。"
        )

    # 外貌堆砌
    for position, value in paragraphs_of(narration):
        found = [term for term in APPEARANCE_TERMS if term in value]
        if len(found) >= 3:
            warnings.append(
                f"外貌堆砌，第 {line_no(text, position)} 行，一段里有 {'、'.join(found[:6])}。"
                "只抓一处，让它跟着看的人走。"
            )

    # 一段里连排的小动作
    for position, value in paragraphs_of(narration):
        found = [m.group() for m in EMPTY_ACTIONS.finditer(value)]
        if len(found) >= 3:
            warnings.append(
                f"小动作连排，第 {line_no(text, position)} 行，{'、'.join(found[:5])}。"
                "留一个带态度的，其余删掉。"
            )

    # 一段里连排的廉价转折
    for position, value in paragraphs_of(narration):
        found = [m.group() for m in SUDDEN.finditer(value)]
        if len(found) >= 3:
            warnings.append(
                f"廉价转折连排，第 {line_no(text, position)} 行，{'、'.join(found[:5])}。删掉，让事情自己发生。"
            )

    # 给抽象名词配具体动词的抒情，脚本只认得出常见的几种
    for match in list(ABSTRACT_LYRIC.finditer(narration))[:4]:
        warnings.append(
            f"疑似抽象抒情，第 {line_no(text, match.start())} 行，“{excerpt(match.group(), 30)}”。"
            "这是硬禁令，写的确实是抽象的东西就改成人做了什么、发生了什么。"
        )

    # 密度类提醒
    density_checks = (
        (EMPTY_ACTIONS, 5.0, "不带态度的小动作", "每一处问它带没带人物的意图，不带就删或换。"),
        (EMOTION_LABELS, 4.0, "情绪标签", "动作已经写出情绪的地方删掉解释，把感到什么换成他在算什么、怕什么。"),
        (HEDGES, 8.0, "模糊词", "似乎、仿佛、一丝、一抹这类词删到必要的几处。"),
        (SUDDEN, 4.0, "廉价转折", "突然、就在这时这类词删掉，让事情自己发生。"),
        (TAG_ADVERBS, 3.0, "带副词的对话提示语", "多数换成“说”或一个动作。"),
    )
    for pattern, limit, label, advice in density_checks:
        hits = list(pattern.finditer(narration))
        density = per_thousand(len(hits), total)
        if len(hits) >= 4 and density > limit:
            top = "、".join(
                f"{term} {count} 次"
                for term, count in collections.Counter(m.group() for m in hits).most_common(4)
            )
            warnings.append(f"{label}偏密，共 {len(hits)} 处，每千字 {density:.1f} 处。{top}。{advice}")

    # 排比
    for match in anaphora_runs(narration)[:3]:
        warnings.append(
            f"三连以上同构排比，第 {line_no(text, match.start())} 行，“{excerpt(match.group())}”。"
            "留两项，第三项换说法或删掉。"
        )

    # 名词化
    for match in [m for p in NOMINALIZATION_PATTERNS for m in p.finditer(narration)][:3]:
        warnings.append(
            f"名词化句式，第 {line_no(text, match.start())} 行，“{excerpt(match.group(), 30)}”。还原成直接的动词。"
        )

    # 连词
    conjunction_hits = [m for term in CONJUNCTIONS for m in re.finditer(term, narration)]
    if narration_han >= 600 and per_thousand(len(conjunction_hits), narration_han) > 7:
        top = "、".join(
            f"{term} {count} 次"
            for term, count in collections.Counter(m.group() for m in conjunction_hits).most_common(4)
        )
        warnings.append(
            f"叙述里连词偏密，每千字 {per_thousand(len(conjunction_hits), narration_han):.1f} 个。{top}。删掉一半试试。"
        )

    # 句长
    cv = sentence_cv(narration)
    if cv and cv[0] < 0.40:
        warnings.append(
            f"叙述的 {cv[1]} 个句子长短过于接近（变异系数 {cv[0]:.2f}）。放开几句，压短几句，让长短跟着事情的密度走。"
        )

    # 段落
    paragraphs = paragraphs_of(prose)
    long_paragraphs = [(position, value) for position, value in paragraphs if han_count(value) > 300]
    if long_paragraphs:
        lines = "、".join(str(line_no(text, position)) for position, _ in long_paragraphs[:6])
        warnings.append(f"超过三百字的段落 {len(long_paragraphs)} 个，第 {lines} 行。手机上读起来是一堵墙，按动作或话轮分开。")

    narration_paragraphs = [
        (position, value) for position, value in paragraphs_of(narration) if han_count(value) >= 2
    ]
    if len(narration_paragraphs) >= 12:

        def opener_of(value: str) -> str:
            han = re.sub(r"[^一-鿿]", "", value)
            return han[:1] if han[:1] in "他她我它" else han[:2]

        openers = collections.Counter(opener_of(value) for _, value in narration_paragraphs)
        opener, count = openers.most_common(1)[0]
        if opener and count / len(narration_paragraphs) >= 0.35:
            warnings.append(
                f"叙述段落有 {count / len(narration_paragraphs):.0%} 以“{opener}”开头。换几段从动作、物件或别人的反应起。"
            )
        single = sum(
            1 for _, value in narration_paragraphs if len(re.findall(r"[。！？!?]", value)) <= 1 and han_count(value) <= 20
        )
        if single / len(narration_paragraphs) >= 0.6:
            warnings.append(
                f"叙述段落有 {single / len(narration_paragraphs):.0%} 是二十字以内的单句段，像在敲鼓点。把顺着读得下去的合并。"
            )

    # 设定说明段
    for position, value in paragraphs_of(narration):
        if han_count(value) < 80:
            continue
        hits = [marker for marker in SETTING_MARKERS if marker in value]
        if len(hits) >= 4:
            warnings.append(
                f"疑似设定说明段，第 {line_no(text, position)} 行，出现 {'、'.join(hits[:6])}。"
                "设定等人物碰到再讲，改成让人物撞上去。"
            )

    # 章末，取全文最后两段里属于叙述的部分
    spans = [m.span() for m in re.finditer(r"[^\n]+", prose) if han_count(m.group()) >= 4][-2:]
    tail = [narration[start:end].strip(" \t　") for start, end in spans]
    for value in tail:
        for pattern in ENDING_PATTERNS:
            match = pattern.search(value)
            if match:
                warnings.append(
                    f"章末疑似预告或升华，“{excerpt(value, 44)}”。把最后一句换成一件事，或者删掉这一段再读。"
                )
                break
        else:
            continue
        break

    # 对白占比
    if total >= 800:
        ratio = stats["对白占比"]
        if ratio < 0.08:
            warnings.append(f"对白只占 {ratio:.0%}。这一章不是独处戏的话，看看是不是概述太多、场景太少。")
        elif ratio > 0.75:
            warnings.append(f"对白占 {ratio:.0%}。看看人物说话时在做什么、在哪里，有没有读者需要的心理。")

    # 字数
    if target:
        deviation = (total - target) / target
        stats["偏离"] = deviation
        if deviation < -tolerance:
            warnings.append(
                f"字数 {total}，比目标 {target} 少 {-deviation:.0%}。加事不加词，加一个阻力、一个旁人的反应、一笔心里的账。"
            )
        elif deviation > tolerance:
            warnings.append(
                f"字数 {total}，比目标 {target} 多 {deviation:.0%}。先删重复，再看是不是装了两章的事。"
            )

    return failures, warnings, stats


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(description="检查小说章节的硬禁令、模型套语和网文常见毛病")
    parser.add_argument("paths", nargs="+", help="章节文件，Markdown 或文本，可以传多个")
    parser.add_argument("--target", type=int, default=None, help="章均目标字数，按汉字计")
    parser.add_argument("--tolerance", type=float, default=0.15, help="字数允许偏离的比例，默认 0.15")
    args = parser.parse_args()

    failed = False
    for raw in args.paths:
        path = Path(raw)
        if len(args.paths) > 1:
            print(f"\n===== {path.name} =====")
        try:
            failures, warnings, stats = check(path, args.target, args.tolerance)
        except OSError as error:
            print(f"无法读取 {path}。{error}", file=sys.stderr)
            failed = True
            continue

        summary = f"汉字数 {stats['汉字数']}，对白占比 {stats['对白占比']:.0%}，模型套语 {stats.get('套语', 0)} 处"
        if "偏离" in stats:
            summary += f"，目标 {args.target} 字，偏离 {stats['偏离']:+.0%}"
        print(summary)
        if failures:
            failed = True
            print("\n需要修改")
            for item in failures:
                print(f"- {item}")
        if warnings:
            print("\n需要人工判断")
            for item in warnings:
                print(f"- {item}")
        if not failures and not warnings:
            print("\n未发现这份检查器覆盖的问题。它只认形状，不能替你判断这一章有没有人。")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
