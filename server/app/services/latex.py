from dataclasses import dataclass
from datetime import date
from pathlib import Path
from string import Template


@dataclass(frozen=True)
class LatexItem:
    type: str
    title: str
    org: str | None
    start_date: date | None
    end_date: date | None
    bullets: list[str]
    category: str | None = None


@dataclass(frozen=True)
class LatexProfile:
    full_name: str | None
    contact_email: str | None
    phone: str | None
    location: str | None
    linkedin_url: str | None
    github_url: str | None
    leetcode_url: str | None
    portfolio_url: str | None


_ESCAPES = {
    "\\": r"\textbackslash{}",
    "{": r"\{",
    "}": r"\}",
    "$": r"\$",
    "&": r"\&",
    "#": r"\#",
    "%": r"\%",
    "_": r"\_",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_SECTION_NAMES = {
    "experience": "Experience",
    "project": "Projects",
    "skill": "Skills",
    "education": "Education",
    "certification": "Certifications",
}
_TEMPLATE = Path(__file__).parents[1] / "latex_templates" / "ats_resume.tex.tpl"


def escape_latex(value: str) -> str:
    return "".join(_ESCAPES.get(character, character) for character in value)


def _date(value: date | None) -> str:
    return value.strftime("%b %Y") if value else ""


def _render_item(item: LatexItem) -> str:
    heading = escape_latex(item.title)
    if item.org:
        heading += rf" \hfill {escape_latex(item.org)}"
    dates = " -- ".join(value for value in (_date(item.start_date), _date(item.end_date)) if value)
    if dates:
        heading += rf" \\ {escape_latex(dates)}"
    rows = [rf"\textbf{{{heading}}}"]
    if item.bullets:
        rows.extend(
            (
                r"\begin{itemize}",
                "\n".join(rf"  \item {escape_latex(value)}" for value in item.bullets),
                r"\end{itemize}",
            )
        )
    return "\n".join(rows)


def _render_skills(items: list[LatexItem]) -> str:
    groups: dict[str, list[str]] = {}
    for item in items:
        groups.setdefault(item.category or "Skills", []).append(escape_latex(item.title))
    return "\n".join(
        rf"\textbf{{{escape_latex(category)}:}} " + ", ".join(names)
        for category, names in groups.items()
    )


def _render_header(profile: LatexProfile | None) -> str:
    if profile is None:
        return ""
    name = escape_latex(profile.full_name or profile.contact_email or "")
    contacts = [
        escape_latex(value)
        for value in (profile.contact_email, profile.phone, profile.location)
        if value
    ]
    contacts.extend(
        rf"\href{{\detokenize{{{value}}}}}{{{escape_latex(value)}}}"
        for value in (
            profile.linkedin_url,
            profile.github_url,
            profile.leetcode_url,
            profile.portfolio_url,
        )
        if value
    )
    rows = []
    if name:
        rows.append(rf"\centerline{{\LARGE \textbf{{{name}}}}}")
    if contacts:
        rows.append("\\\\\n".join(contacts))
    return "\n".join(rows)


def render_resume(items: list[LatexItem], profile: LatexProfile | None = None) -> str:
    sections = []
    for item_type, title in _SECTION_NAMES.items():
        rows = [item for item in items if item.type == item_type]
        if rows:
            content = _render_skills(rows) if item_type == "skill" else "\n".join(
                _render_item(item) for item in rows
            )
            sections.append(rf"\section*{{{title}}}" + "\n" + content)
    return Template(_TEMPLATE.read_text()).substitute(
        header=_render_header(profile), sections="\n".join(sections)
    )
