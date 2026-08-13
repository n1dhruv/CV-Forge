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
    "education": "Education",
    "skill": "Skills",
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
    bullets = "\n".join(rf"  \item {escape_latex(value)}" for value in item.bullets)
    return "\n".join((rf"\textbf{{{heading}}}", r"\begin{itemize}", bullets, r"\end{itemize}"))


def render_resume(items: list[LatexItem]) -> str:
    sections = []
    for item_type, title in _SECTION_NAMES.items():
        rows = [_render_item(item) for item in items if item.type == item_type]
        if rows:
            sections.append(rf"\section*{{{title}}}" + "\n" + "\n".join(rows))
    return Template(_TEMPLATE.read_text()).substitute(sections="\n".join(sections))
