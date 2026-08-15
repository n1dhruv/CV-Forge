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
    details: str | None = None
    tags: list[str] | None = None
    links: list[tuple[str, str]] | None = None


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
    "|": r"\textbar{}",
}
_SECTION_NAMES = {
    "skill": "Skills",
    "experience": "Experience",
    "project": "Projects",
    "education": "Education",
    "certification": "Certifications",
}
_TEMPLATE = Path(__file__).parents[1] / "latex_templates" / "ats_resume.tex.tpl"


def escape_latex(value: str) -> str:
    return "".join(_ESCAPES.get(character, character) for character in value)


def _tex_safe_url(value: str) -> str:
    for character, encoded in (("\\", "%5C"), ("{", "%7B"), ("}", "%7D"), ("~", "%7E"), ("^", "%5E")):
        value = value.replace(character, encoded)
    return "".join(rf"\{character}" if character in "%_#&$" else character for character in value)


def _date(value: date | None) -> str:
    return value.strftime("%b %Y") if value else ""


def _dates(item: LatexItem) -> str:
    if item.start_date:
        return f"{_date(item.start_date)} -- {_date(item.end_date) or 'Present'}"
    return _date(item.end_date)


def _render_links(item: LatexItem) -> str:
    return " ".join(
        rf"[\href{{{_tex_safe_url(url)}}}{{{escape_latex(label)}}}]"
        for label, url in item.links or []
    )


def _render_item(item: LatexItem) -> str:
    heading = rf"\textbf{{{escape_latex(item.title)}}}"
    links = _render_links(item)
    if links:
        heading += " " + links
    if item.type == "education" and item.org:
        heading += ", " + escape_latex(item.org)
    right = (
        escape_latex(", ".join(item.tags or []))
        if item.type == "project" and item.tags
        else escape_latex(_dates(item))
    )
    if right:
        heading += rf" \hfill {right}"
    rows = [heading]
    if item.org and item.type != "education":
        rows.append(r"\\[-1pt] " + escape_latex(item.org))
    if item.details:
        rows.append(r"\\[-1pt] " + escape_latex(item.details))
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
        rf"\textbf{{{escape_latex(category)}:}} " + ", ".join(names) + r"\par"
        for category, names in groups.items()
    )


def _render_header(profile: LatexProfile | None) -> str:
    if profile is None:
        return ""
    name = escape_latex(profile.full_name or "")
    contacts = []
    if profile.phone:
        contacts.append(escape_latex(profile.phone))
    if profile.contact_email:
        contacts.append(
            rf"\href{{{_tex_safe_url('mailto:' + profile.contact_email)}}}"
            rf"{{{escape_latex(profile.contact_email)}}}"
        )
    if profile.location:
        contacts.append(escape_latex(profile.location))
    contacts.extend(
        rf"\href{{{_tex_safe_url(value)}}}{{{label}}}"
        for label, value in (
            ("LinkedIn", profile.linkedin_url),
            ("Portfolio", profile.portfolio_url),
            ("GitHub", profile.github_url),
            ("LeetCode", profile.leetcode_url),
        )
        if value
    )
    rows = []
    if name:
        rows.append(rf"{{\Large\bfseries\MakeUppercase{{{name}}}}}")
    if contacts:
        rows.append(r"\\[2pt] " + r" \textbar\ ".join(contacts))
    return "\n".join((r"\begin{center}", *rows, r"\end{center}"))


def render_resume(items: list[LatexItem], profile: LatexProfile | None = None) -> str:
    sections = []
    for item_type, title in _SECTION_NAMES.items():
        rows = [item for item in items if item.type == item_type]
        if rows:
            content = _render_skills(rows) if item_type == "skill" else "\n".join(
                _render_item(item) for item in rows
            )
            sections.append(rf"\resumesection{{\MakeUppercase{{{title}}}}}" + "\n" + content)
    return Template(_TEMPLATE.read_text()).substitute(
        header=_render_header(profile), sections="\n".join(sections)
    )
