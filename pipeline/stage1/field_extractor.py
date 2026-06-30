from __future__ import annotations
import re
from typing import Any

Tagged = dict[str, Any]

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?<!\d)(\+?[\d][\d\s\-().]{6,}\d)(?!\d)")
_LINKEDIN_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w\-]+", re.IGNORECASE)
_GITHUB_URL_RE = re.compile(r"(?:https?://)?(?:www\.)?github\.com/[\w\-]+", re.IGNORECASE)
_NAME_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z '.]{1,50}$")

_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
_DPART = rf"(?:\d{{1,2}}/\d{{4}}|{_MONTH}\s+\d{{4}}|\d{{4}})"
_DATE_RANGE_RE = re.compile(rf"^\s*({_DPART})\s*(?:[-–]|to)\s*({_DPART}|[Pp]resent)\s*$", re.IGNORECASE)
_COMPANY_TITLE_RE = re.compile(r"^(.+?)\s*[-–]\s*(.+)$")
_EDU_RE = re.compile(
    r"^(B\.Tech|B\.E\.?|B\.Eng\.?|B\.S\.?|B\.A\.?|B\.Sc\.?|B\.Com|B\.Arch\.?|BS|BA|BE|"
    r"M\.Tech|M\.E\.?|M\.Eng\.?|M\.S\.?|M\.A\.?|M\.Sc\.?|M\.Arch\.?|MBA|MS|MA|ME|MFA|"
    r"Ph\.D\.?|PhD|LLB|LLM|MD|DDS|JD|"
    r"A\.A\.S?\.?|AAS?|AS|AA)([\s,].*)$",
    re.IGNORECASE,
)

_SECTION_NAMES = {
    "summary", "professional summary", "objective", "profile", "about",
    "experience", "work history", "professional experience", "work experience", "employment history",
    "education", "academic background", "academic qualifications",
    "skills", "technical skills", "core competencies", "key skills",
    "references", "reference",
    "certifications", "certification", "projects", "project",
    "languages", "achievements", "awards",
}
_SECTION_NAMES_SORTED = sorted(_SECTION_NAMES, key=len, reverse=True)


def _t(value: Any, method: str, source: str) -> Tagged:
    return {"value": value, "method": method, "source": source}


def _section_key(header: str) -> str:
    h = header.lower().strip()
    if h in ("summary", "professional summary", "objective", "profile", "about"):
        return "summary"
    if h in ("experience", "work history", "professional experience", "work experience", "employment history"):
        return "experience"
    if h in ("education", "academic background", "academic qualifications"):
        return "education"
    if h in ("skills", "technical skills", "core competencies", "key skills"):
        return "skills"
    if h in ("references", "reference"):
        return "references"
    return h


def _match_section_header(line: str) -> str | None:
    low = line.lower().strip()
    for sname in _SECTION_NAMES_SORTED:
        if low == sname:
            return sname
        if low.startswith(sname) and len(low) > len(sname) and low[len(sname)] in ": ":
            return sname
    return None


def _split_sections(text: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    for line in text.strip().splitlines():
        s = line.strip()
        matched = _match_section_header(s)
        if matched:
            current = _section_key(matched)
            sections.setdefault(current, [])
        else:
            sections.setdefault(current, []).append(s)
    return sections


def _extract_links_from_resume(text: str) -> dict[str, str | None]:
    linkedin = github = None
    for line in text.splitlines():
        if not linkedin:
            m = _LINKEDIN_URL_RE.search(line)
            if m:
                linkedin = m.group()
        if not github:
            m = _GITHUB_URL_RE.search(line)
            if m:
                github = m.group()
        if linkedin and github:
            break
    return {"linkedin": linkedin, "github": github, "portfolio": None, "other": []}


def _extract_name_from_resume(sections: dict[str, list[str]]) -> str | None:
    for line in sections.get("header", []):
        s = line.strip()
        if s and _NAME_LINE_RE.match(s) and not _EMAIL_RE.search(s) and not _PHONE_RE.search(s) and len(s.split()) >= 2:
            return s
    return None


def _extract_contacts(text: str) -> tuple[list[str], list[str]]:
    emails: list[str] = []
    phones: list[str] = []
    for line in text.splitlines():
        if "refer" in line.lower():
            continue
        for m in _EMAIL_RE.finditer(line):
            emails.append(m.group())
        for m in _PHONE_RE.finditer(line):
            phones.append(m.group().strip())
    return emails, phones


def _parse_experience(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    current: dict | None = None
    for line in lines:
        if not line:
            continue
        dm = _DATE_RANGE_RE.match(line)
        if dm:
            if current is not None:
                current["start"] = dm.group(1)
                current["end"] = None if dm.group(2).lower() == "present" else dm.group(2)
            continue
        cm = None if line[0] in "•*" else _COMPANY_TITLE_RE.match(line)
        if cm:
            if current is not None:
                entries.append(current)
            current = {"company": cm.group(1).strip(), "title": cm.group(2).strip(), "start": None, "end": None, "summary": ""}
        elif current is not None:
            detail = line.lstrip("•- ").strip()
            if detail:
                current["summary"] = (current["summary"] + " " + detail).strip()
    if current is not None:
        entries.append(current)
    return entries


def _parse_education(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line in lines:
        if not line:
            continue
        m = _EDU_RE.match(line)
        if not m:
            continue
        degree = m.group(1)
        rest = m.group(2).strip().lstrip(",").strip()
        parts = [p.strip() for p in rest.split(",") if p.strip()]
        end_year: int | None = None
        institution = ""
        field = ""
        for part in reversed(parts):
            if re.match(r"^\d{4}$", part):
                end_year = int(part)
            elif not institution:
                institution = part
            elif not field:
                field = part
        if institution:
            entries.append({"institution": institution, "degree": degree, "field": field or None, "end_year": end_year})
    return entries


def _parse_skills(lines: list[str]) -> list[str]:
    text = " ".join(lines)
    return [t.strip() for t in re.split(r"[,\n|]+", text) if t.strip()]


def _parse_certifications(lines: list[str]) -> list[dict]:
    entries: list[dict] = []
    for line in lines:
        s = line.lstrip("••-– ").strip()
        if not s:
            continue
        year_m = re.search(r"\((\d{4})\)\s*$", s)
        year = int(year_m.group(1)) if year_m else None
        name = re.sub(r"\s*\(\d{4}\)\s*$", "", s).strip() if year_m else s
        if name:
            entries.append({"name": name, "year": year})
    return entries


def extract(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for rec in records:
        out: dict[str, list[Tagged]] = {
            "full_name": [], "emails": [], "phones": [], "location": [],
            "headline": [], "years_experience": [], "current_company": [],
            "title": [], "links": [], "skills": [], "experience": [], "education": [],
            "certifications": [],
        }
        row = rec["csv"]
        name = row.get("name", "").strip()
        def _rv(key: str) -> str:
            return (row.get(key) or "").strip()

        if name:
            out["full_name"].append(_t(name, "direct", "csv"))
        if _rv("email"):
            out["emails"].append(_t(_rv("email"), "direct", "csv"))
        if _rv("phone"):
            out["phones"].append(_t(_rv("phone"), "direct", "csv"))
        city = _rv("location_city")
        region = _rv("location_region")
        country = _rv("location_country")
        if city or region or country:
            out["location"].append(_t({"city": city or None, "region": region or None, "country": country or None}, "direct", "csv"))
        if _rv("headline"):
            out["headline"].append(_t(_rv("headline"), "direct", "csv"))
        yoe = _rv("years_experience")
        if yoe:
            try:
                out["years_experience"].append(_t(int(yoe), "direct", "csv"))
            except ValueError:
                pass
        if _rv("current_company"):
            out["current_company"].append(_t(_rv("current_company"), "direct", "csv"))
        if _rv("title"):
            out["title"].append(_t(_rv("title"), "direct", "csv"))
        out["links"].append(_t({
            "linkedin": _rv("linkedin_url") or None,
            "github": _rv("github_url") or None,
            "portfolio": _rv("portfolio_url") or None,
            "other": [],
        }, "direct", "csv"))

        gh = rec.get("github_parsed")
        if gh is not None:
            if gh.get("name"):
                out["full_name"].append(_t(gh["name"], "direct", "github"))
            if gh.get("email"):
                out["emails"].append(_t(gh["email"], "direct", "github"))
            if gh.get("location"):
                parts = [p.strip() for p in gh["location"].split(",")]
                gh_city = parts[0]
                gh_country = parts[-1] if len(parts) >= 2 else None
                out["location"].append(_t({"city": gh_city, "region": None, "country": gh_country}, "direct", "github"))
            if gh.get("bio"):
                out["headline"].append(_t(gh["bio"], "direct", "github"))
            if gh.get("company"):
                out["current_company"].append(_t(gh["company"], "direct", "github"))
            link_val = {"linkedin": None, "github": gh.get("html_url"), "portfolio": gh.get("blog") or None, "other": []}
            out["links"].append(_t(link_val, "direct", "github"))
            for repo in gh.get("repos", []):
                lang = repo.get("language")
                if lang:
                    out["skills"].append(_t(lang, "language_inferred", "github"))

        resume = rec.get("resume_raw")
        if resume is not None:
            emails, phones = _extract_contacts(resume)
            for e in emails:
                out["emails"].append(_t(e, "regex_extracted", "resume"))
            for p in phones:
                out["phones"].append(_t(p, "regex_extracted", "resume"))
            sections = _split_sections(resume)
            name_from_resume = _extract_name_from_resume(sections)
            if name_from_resume:
                out["full_name"].append(_t(name_from_resume, "section_heuristic", "resume"))
            resume_links = _extract_links_from_resume(resume)
            if resume_links["linkedin"] or resume_links["github"]:
                out["links"].append(_t(resume_links, "regex_extracted", "resume"))
            for entry in _parse_experience(sections.get("experience", [])):
                out["experience"].append(_t(entry, "section_heuristic", "resume"))
            for entry in _parse_education(sections.get("education", [])):
                out["education"].append(_t(entry, "section_heuristic", "resume"))
            for skill in _parse_skills(sections.get("skills", [])):
                out["skills"].append(_t(skill, "regex_extracted", "resume"))
            for cert in _parse_certifications(sections.get("certifications", [])):
                out["certifications"].append(_t(cert, "section_heuristic", "resume"))

        rec["extracted"] = out
    return records
