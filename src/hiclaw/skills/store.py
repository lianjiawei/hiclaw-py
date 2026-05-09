from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from hiclaw.config import SKILLS_DIR


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


# ---------------------------------------------------------------------------
# Frontmatter parser
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---', re.DOTALL)


def _parse_frontmatter(content: str) -> dict[str, object]:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return {}

    raw = match.group(1)
    result: dict[str, object] = {}

    for line in raw.split('\n'):
        line = line.strip()
        if not line or ':' not in line:
            continue
        key, _, value = line.partition(':')
        key = key.strip()
        value = value.strip()

        if value.startswith('[') and value.endswith(']'):
            inner = value[1:-1]
            items = [
                item.strip().strip("'").strip('"')
                for item in inner.split(',')
                if item.strip()
            ]
            result[key] = items
        elif (value.startswith('"') and value.endswith('"')) or \
             (value.startswith("'") and value.endswith("'")):
            result[key] = value[1:-1]
        else:
            result[key] = value

    return result


def _get_body(content: str) -> str:
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return content.strip()
    return content[match.end():].strip()


# ---------------------------------------------------------------------------
# Skill loader with mtime-based hot-reload cache
# ---------------------------------------------------------------------------

class SkillLoader:
    """扫描 SKILLS_DIR 目录，自动发现 skill 定义并缓存。"""

    def __init__(self, skills_dir: Path):
        self._skills_dir = skills_dir
        self._cache: dict[str, tuple[float, SkillDefinition, str]] = {}

    # ---- internal helpers ------------------------------------------------

    def _scan_files(self) -> list[Path]:
        try:
            return sorted(
                [p for p in self._skills_dir.glob('**/*.md') if p.is_file()],
                key=lambda p: p.name,
            )
        except OSError:
            return []

    @staticmethod
    def _first_str(value: object, default: str = '') -> str:
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
        return default

    @staticmethod
    def _as_tuple(value: object) -> tuple[str, ...]:
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        if isinstance(value, str):
            items = [v.strip() for v in value.split(',') if v.strip()]
            return tuple(items)
        return ()

    def _cache_key(self, file_path: Path) -> str:
        """Use relative path as cache key to avoid filename collisions across subdirectories."""
        try:
            return str(file_path.relative_to(self._skills_dir))
        except ValueError:
            return file_path.name

    def _load_file(self, file_path: Path) -> tuple[SkillDefinition, str] | None:
        try:
            raw = file_path.read_text(encoding='utf-8')
        except Exception:
            return None

        fm = _parse_frontmatter(raw)

        # 没有 frontmatter name 的不是 skill 定义（如模板文件）
        if 'name' not in fm:
            return None

        body = _get_body(raw)

        name = self._first_str(fm.get('name', ''), file_path.stem)
        title = self._first_str(fm.get('title', ''), file_path.stem)
        description = self._first_str(fm.get('description', ''), '')
        keywords = self._as_tuple(fm.get('keywords', ()))
        aliases = self._as_tuple(fm.get('aliases', ()))

        return SkillDefinition(
            name=name,
            title=title,
            description=description,
            file_name=str(file_path.relative_to(self._skills_dir)),
            keywords=keywords,
            aliases=aliases,
        ), body

    # ---- public API ------------------------------------------------------

    def get_all(self) -> list[SkillDefinition]:
        definitions: list[SkillDefinition] = []
        for file_path in self._scan_files():
            mtime = file_path.stat().st_mtime
            key = self._cache_key(file_path)
            if key in self._cache and self._cache[key][0] >= mtime:
                definitions.append(self._cache[key][1])
                continue
            loaded = self._load_file(file_path)
            if loaded is not None:
                definition, body = loaded
                self._cache[key] = (mtime, definition, body)
                definitions.append(definition)
        return definitions

    def get_skill(self, name: str) -> SkillDefinition | None:
        normalized = name.strip().lower()
        for skill in self.get_all():
            if normalized == skill.name.lower() or normalized in (a.lower() for a in skill.aliases):
                return skill
        return None

    def get_body(self, skill: SkillDefinition) -> str:
        key = self._cache_key(skill.file_path)
        if key in self._cache:
            return self._cache[key][2]
        raw = skill.file_path.read_text(encoding='utf-8')
        return _get_body(raw)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_loader = SkillLoader(SKILLS_DIR)


# ---------------------------------------------------------------------------
# 对外 API（保持原有签名不变）
# ---------------------------------------------------------------------------

def list_skills() -> list[SkillDefinition]:
    return _loader.get_all()


def get_skill(name: str) -> SkillDefinition | None:
    return _loader.get_skill(name)


def select_skills(prompt: str, max_skills: int = 3) -> list[SkillDefinition]:
    text = prompt.lower()
    selected: list[SkillDefinition] = []

    explicit_names = {part[1:] for part in text.split() if part.startswith('#')}
    for explicit_name in explicit_names:
        skill = get_skill(explicit_name)
        if skill and skill not in selected:
            selected.append(skill)

    if len(selected) >= max_skills:
        return selected[:max_skills]

    all_skills = list_skills()
    scored: list[tuple[int, SkillDefinition]] = []
    for skill in all_skills:
        if skill in selected:
            continue
        score = sum(1 for keyword in skill.keywords if keyword.lower() in text)
        score += sum(1 for alias in skill.aliases if alias.lower() in text)
        if score > 0:
            scored.append((score, skill))

    scored.sort(key=lambda item: item[0], reverse=True)
    for _, skill in scored:
        if len(selected) >= max_skills:
            break
        selected.append(skill)

    return selected


def build_skill_prompt(prompt: str) -> tuple[list[SkillDefinition], str]:
    selected_skills = select_skills(prompt)
    if not selected_skills:
        return [], ''

    parts: list[str] = ['下面是本轮问题匹配到的 skill，请优先遵循这份专长说明：']
    for skill in selected_skills:
        if not skill.file_path.exists():
            continue
        content = _loader.get_body(skill)
        parts.append(f'\n[Skill: {skill.name} | {skill.title}]\n{content}')

    return selected_skills, '\n'.join(parts).strip()
