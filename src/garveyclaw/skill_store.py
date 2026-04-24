from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from garveyclaw.config import SKILLS_DIR


@dataclass(frozen=True)
class SkillDefinition:
    """描述一个可以注入到 Agent 的本地 skill。"""

    name: str
    title: str
    description: str
    file_name: str
    keywords: tuple[str, ...]
    aliases: tuple[str, ...] = ()

    @property
    def file_path(self) -> Path:
        return SKILLS_DIR / self.file_name


SKILL_DEFINITIONS: tuple[SkillDefinition, ...] = (
    SkillDefinition(
        name="table_analysis",
        title="表格数据分析",
        description="读取表格、提取关键字段、校验汇总结果并给出判断。",
        file_name="table_analysis_skill.md",
        keywords=(
            "表格",
            "excel",
            "xlsx",
            "csv",
            "数据",
            "统计",
            "汇总",
            "合计",
            "总和",
            "平均",
            "比例",
            "校验",
            "核对",
            "判断",
            "分析",
            "提取",
        ),
        aliases=("table", "spreadsheet", "excel"),
    ),
)


def list_skills() -> tuple[SkillDefinition, ...]:
    """返回当前项目内置的 skill 定义。"""

    return SKILL_DEFINITIONS


def get_skill(name: str) -> SkillDefinition | None:
    """按名称或别名查找一个 skill。"""

    normalized = name.strip().lower()
    for skill in SKILL_DEFINITIONS:
        if normalized == skill.name or normalized in skill.aliases:
            return skill
    return None


def select_skills(prompt: str, max_skills: int = 1) -> list[SkillDefinition]:
    """根据用户问题做轻量匹配，挑选本轮需要注入的 skill。"""

    text = prompt.lower()
    selected: list[SkillDefinition] = []

    # 支持用户用 #table_analysis 或 #table 显式点名 skill。
    explicit_names = {part[1:] for part in text.split() if part.startswith("#")}
    for explicit_name in explicit_names:
        skill = get_skill(explicit_name)
        if skill and skill not in selected:
            selected.append(skill)

    if len(selected) >= max_skills:
        return selected[:max_skills]

    scored: list[tuple[int, SkillDefinition]] = []
    for skill in SKILL_DEFINITIONS:
        if skill in selected:
            continue
        score = sum(1 for keyword in skill.keywords if keyword.lower() in text)
        if score > 0:
            scored.append((score, skill))

    scored.sort(key=lambda item: item[0], reverse=True)
    for _, skill in scored:
        if len(selected) >= max_skills:
            break
        selected.append(skill)

    return selected


def build_skill_prompt(prompt: str) -> tuple[list[SkillDefinition], str]:
    """把命中的 skill 内容整理成可以拼进 system prompt 的文本。"""

    selected_skills = select_skills(prompt)
    if not selected_skills:
        return [], ""

    parts: list[str] = ["下面是本轮问题匹配到的 skill，请优先遵循这份专长说明："]
    for skill in selected_skills:
        if not skill.file_path.exists():
            continue
        content = skill.file_path.read_text(encoding="utf-8").strip()
        parts.append(f"\n[Skill: {skill.name} | {skill.title}]\n{content}")

    return selected_skills, "\n".join(parts).strip()
