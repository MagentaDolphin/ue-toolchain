"""Delivery gate for the ue-design-skills plugin bundle.

Checks the shipping surface of a plugin tree against rules that the
depersonalization work must satisfy. Output is ASCII only.

    python _gate/gate.py [plugin_root]
    python _gate/gate.py --list-rules

Exit code 0 when clean, 1 when any rule fires.

Design notes
------------
The scan surface is a WHITELIST, not "everything minus exclusions". A blacklist
lets an unscanned directory appear by accident; rule P11 closes the remaining
hole by rejecting any top-level entry that is not on the known list. So
`_gate/` is unscanned because it is not shipped content, and nothing else can
quietly join it.

This gate cannot detect a fabricated claim. Green means the form is right, not
that the entry is true.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Scan surface
# --------------------------------------------------------------------------

SCAN_DIRS = ('.claude-plugin', 'skills')
SCAN_ROOT_FILES = ('README.md', 'LICENSE')
ALLOWED_TOP_LEVEL = {'.claude-plugin', 'skills', '_gate', 'README.md',
                     'LICENSE', '.gitignore', 'catalog.json'}

# Harness neutrality. The skills are plain Markdown with YAML frontmatter and
# must be usable by any agent or runner. A vendor manifest is an adapter that
# sits outside skills/ -- content that names one harness cannot be run by
# another, so naming one inside skills/ is a portability defect, not a style
# preference.
HARNESS_TOKENS = (
    r'\$\{CLAUDE_[A-Z_]*\}',
    r'\bClaude\b',
    r'\bCursor\b',
    r'\bCopilot\b',
    r'(?<![A-Za-z0-9_./-])\.claude/',
)

# Engine tool surface. The first-party agent-tool layer shipped with the editor
# is Experimental and says so: "APIs and data formats are subject to change at
# any time". A recipe that names a toolset, a meta-tool or an endpoint dates
# itself to one engine build and fails silently on the next -- the tool is
# simply absent, which reads as "nothing found here" rather than as an error.
# Measured surface drift is why this is a rule and not advice: one editor
# session exposed 53 toolsets from 21 aggregated plugins, and the visible tool
# count flips between 3 and several hundred on a single project setting.
ENGINE_TOOL_TOKENS = (
    r'\b(?:list_toolsets|describe_toolset|call_tool)\b',
    r'\b[A-Za-z][A-Za-z0-9_]*Toolsets?\b',
    r'\bAgentSkill[A-Za-z]*\b',
    r'\bModelContextProtocol[A-Za-z]*\b',
    r'\b(?:127\.0\.0\.1|localhost)\s*:\s*\d+',
)

TEXT_SUFFIXES = {'.md', '.json', '.txt', '.yaml', '.yml'}
JUNK_SUFFIXES = {'.pyc', '.pyo', '.html', '.htm', '.zip', '.exe', '.dll',
                 '.uasset', '.umap', '.pdb', '.log'}

DONOR_TOKENS = ('Lyra',)

REQUIRED_ENTRY_FIELDS = (
    'Mechanism',
    'Why it is silent',
    'Why the obvious check misses it',
    'Symptom',
    'Detect',
    'Guardrail',
)

# --------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------

RE_ABS_PATH = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]')
RE_CITATION = re.compile(
    r'\b[A-Za-z0-9_./\\-]+\.(?:h|hpp|c|cpp|cs|ini|py|md|uproject|uplugin|json)'
    r'\s*:\s*\d+')
RE_CYRILLIC = re.compile(r'[Ѐ-ӿ]')
RE_WIKILINK = re.compile(r'\[\[')
RE_MD_LINK = re.compile(r'\]\(([^)]+)\)')
RE_HEADING = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
RE_PROVENANCE = re.compile(r'^#{1,6}\s+Provenance\s*$')
RE_BANNER_RULE = re.compile(r'^={10,}\s*$')
RE_ENTRY_FIELD = re.compile(r'^\*\*([^*]+?)[.:]\*\*')
RE_KEBAB = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


@dataclass(frozen=True)
class Violation:
    rule: str
    path: str
    line: int
    text: str


@dataclass(frozen=True)
class Rule:
    id: str
    what: str


RULES = [
    Rule('P01', 'absolute workstation path (drive letter) in shipped file'),
    Rule('P02', 'source citation File.ext:line in shipped file'),
    Rule('P03', 'donor project name outside a Provenance section'),
    Rule('P04', 'Cyrillic character in shipped file'),
    Rule('P05', 'wiki-style [[link]] that resolves to nothing in a plugin'),
    Rule('P06', 'skill frontmatter name missing, not kebab-case, or != folder'),
    Rule('P07', 'skill frontmatter description missing or empty'),
    Rule('P08', 'references/failure-modes.md missing or not linked from SKILL.md'),
    Rule('P09', 'failure-mode entry missing a required field'),
    Rule('P10', 'relative link is broken or escapes the skill directory'),
    Rule('P11', 'unexpected top-level entry in the plugin root'),
    Rule('P12', 'junk or binary file in the shipping surface'),
    Rule('P13', 'skill content names a specific agent harness or vendor'),
    Rule('P14', 'skill lacks the harness-neutral catalog entry it needs to be '
                'discoverable without a vendor manifest'),
    Rule('P15', 'failure-mode entry ids are not sequential in document order'),
    Rule('P16', 'two skills share an entry-id prefix, so the archive resolver '
                'silently collapses them'),
    Rule('P17', 'skill content names an engine tool surface (toolset, meta-tool '
                'or endpoint) that is Experimental and version-bound'),
]

# A rule that never fires on its fixture does not exist. The fixture corpus in
# _gate/test_gate.py asserts one poison per rule; this guards against a rule
# being silently dropped from the list itself.
assert len(RULES) >= 17, 'rule set shrank; a rule was lost'
assert len({r.id for r in RULES}) == len(RULES), 'duplicate rule id'


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def _shipped_files(root: Path):
    """Every file on the shipping surface, whitelist order."""
    for name in SCAN_ROOT_FILES:
        p = root / name
        if p.is_file():
            yield p
    for d in SCAN_DIRS:
        base = root / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob('*')):
            if p.is_file():
                yield p


def _is_text(root: Path, path: Path) -> bool:
    """Whether the line-level rules should read this file.

    Extension is the usual signal, but LICENSE has none. It sat in
    SCAN_ROOT_FILES and was skipped by every line rule for as long as it did
    not exist: a LICENSE carrying an absolute path, a citation, the donor name,
    Cyrillic and a wikilink passed the gate green. A root file on the declared
    surface is text whatever its suffix.
    """
    if path.suffix.lower() in TEXT_SUFFIXES:
        return True
    return path.parent == root and path.name in SCAN_ROOT_FILES


def _banner_provenance_lines(text: str) -> set[int]:
    """1-based line numbers inside a banner-style PROVENANCE section.

    Markdown marks a section with '## Provenance'; a plain-text LICENSE marks
    it with a title between rules of '='. The donor carve-out is about the
    section, not about the syntax that happens to delimit it, so a LICENSE
    stating where the material came from must not be forced to omit the name.
    """
    allowed: set[int] = set()
    lines = text.splitlines()
    inside = False
    i = 0
    n = len(lines)
    while i < n:
        # A banner heading is three lines: rule, title, rule. Reading them one
        # at a time makes the closing rule look like a new heading with an
        # empty title, which closed the section on the line that opened it.
        if (i + 2 < n
                and RE_BANNER_RULE.match(lines[i])
                and RE_BANNER_RULE.match(lines[i + 2])
                and lines[i + 1].strip()):
            inside = lines[i + 1].strip().upper() == 'PROVENANCE'
            i += 3
            continue
        if inside:
            allowed.add(i + 1)
        i += 1
    return allowed


def _provenance_lines(text: str) -> set[int]:
    """1-based line numbers that sit inside a Provenance section."""
    allowed: set[int] = set()
    lines = text.splitlines()
    depth = None
    for i, line in enumerate(lines, 1):
        m = RE_HEADING.match(line)
        if m:
            level = len(m.group(1))
            if depth is not None and level <= depth:
                depth = None
            if RE_PROVENANCE.match(line):
                depth = level
                allowed.add(i)
                continue
        if depth is not None:
            allowed.add(i)
    return allowed


def _frontmatter(text: str) -> dict[str, str] | None:
    if not text.startswith('---\n'):
        return None
    end = text.find('\n---', 4)
    if end == -1:
        return None
    block = text[4:end]
    out: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$', line)
        if m:
            key = m.group(1)
            out[key] = m.group(2).strip()
        elif key and line.strip():
            out[key] = (out[key] + ' ' + line.strip()).strip()
    return out


# --------------------------------------------------------------------------
# Line-level rules
# --------------------------------------------------------------------------

def check_text_rules(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for path in _shipped_files(root):
        if not _is_text(root, path):
            continue
        rel = path.relative_to(root).as_posix()
        text = _read(path)
        suffix = path.suffix.lower()
        if suffix == '.md':
            prov = _provenance_lines(text)
        elif not suffix:
            # LICENSE and friends: no extension, no Markdown headings, but
            # they still carry a PROVENANCE section and it still needs the
            # donor name to say anything honest.
            prov = _banner_provenance_lines(text)
        else:
            prov = set()
        for n, line in enumerate(text.splitlines(), 1):
            if RE_ABS_PATH.search(line):
                out.append(Violation('P01', rel, n, line.strip()))
            m = RE_CITATION.search(line)
            if m:
                out.append(Violation('P02', rel, n, m.group(0)))
            if n not in prov:
                for token in DONOR_TOKENS:
                    if re.search(r'\b' + re.escape(token), line, re.I):
                        out.append(Violation('P03', rel, n, line.strip()))
                        break
            if RE_CYRILLIC.search(line):
                out.append(Violation('P04', rel, n, line.strip()[:60]))
            if RE_WIKILINK.search(line):
                out.append(Violation('P05', rel, n, line.strip()))
    return out


# --------------------------------------------------------------------------
# Structural rules
# --------------------------------------------------------------------------

def check_harness_neutral(root: Path) -> list[Violation]:
    """P13: nothing under skills/ may name a specific agent harness.

    The vendor manifest in .claude-plugin/ is an adapter and is exempt. Skill
    content is not: a recipe that says "run this Claude command" cannot be run
    by another agent, and the reader has no way to translate it.
    """
    out: list[Violation] = []
    base = root / 'skills'
    if not base.is_dir():
        return out
    patterns = [re.compile(p) for p in HARNESS_TOKENS]
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(path.read_text(
                encoding='utf-8', errors='replace').splitlines(), 1):
            for pat in patterns:
                m = pat.search(line)
                if m:
                    out.append(Violation('P13', rel, n,
                                         f'harness-specific token: {m.group(0)}'))
                    break
    return out


def check_engine_tool_surface(root: Path) -> list[Violation]:
    """P17: nothing under skills/ may name the engine's own agent-tool surface.

    P13 keeps the content free of one *harness*; this keeps it free of one
    *engine build*. The distinction matters because the failure looks different:
    a harness token tells the reader to run something they do not have, while a
    toolset name tells them to run something that used to exist. The second is
    quieter -- the tool is missing, the search returns nothing, and "nothing
    found" is indistinguishable from "no problem here", which is the exact
    failure this bundle exists to document.

    Detect recipes may still say what to look for. They may not say which
    first-party tool to look with.
    """
    out: list[Violation] = []
    base = root / 'skills'
    if not base.is_dir():
        return out
    patterns = [re.compile(p) for p in ENGINE_TOOL_TOKENS]
    for path in sorted(base.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(root).as_posix()
        for n, line in enumerate(path.read_text(
                encoding='utf-8', errors='replace').splitlines(), 1):
            for pat in patterns:
                m = pat.search(line)
                if m:
                    out.append(Violation('P17', rel, n,
                                         f'engine tool surface: {m.group(0)}'))
                    break
    return out


def check_catalog(root: Path) -> list[Violation]:
    """P14: catalog.json describes every skill without vendor vocabulary.

    A harness that does not read .claude-plugin/ still needs to know what is
    here and when to reach for it. Without this file the bundle is only usable
    by the one runner whose manifest format we happened to write.
    """
    out: list[Violation] = []
    cat = root / 'catalog.json'
    skills_dir = root / 'skills'
    present = sorted(p.name for p in skills_dir.iterdir()
                     if p.is_dir()) if skills_dir.is_dir() else []
    if not cat.is_file():
        if present:
            out.append(Violation('P14', 'catalog.json', 0,
                                 'missing; skills are not discoverable '
                                 'without a vendor manifest'))
        return out
    try:
        data = json.loads(_read(cat))
    except json.JSONDecodeError as exc:
        out.append(Violation('P14', 'catalog.json', 0, f'invalid JSON: {exc}'))
        return out

    entries = data.get('skills')
    if not isinstance(entries, list):
        out.append(Violation('P14', 'catalog.json', 0,
                             'no "skills" array'))
        return out

    listed = []
    for i, e in enumerate(entries):
        if not isinstance(e, dict):
            out.append(Violation('P14', 'catalog.json', 0,
                                 f'entry {i} is not an object'))
            continue
        name = e.get('id', '')
        listed.append(name)
        for field in ('id', 'path', 'description', 'use_when'):
            if not str(e.get(field, '')).strip():
                out.append(Violation('P14', 'catalog.json', 0,
                                     f'{name or i}: empty {field}'))
        p = str(e.get('path', ''))
        if p and not (root / p / 'SKILL.md').is_file():
            out.append(Violation('P14', 'catalog.json', 0,
                                 f'{name}: path does not hold a SKILL.md: {p}'))
    for missing in sorted(set(present) - set(listed)):
        out.append(Violation('P14', 'catalog.json', 0,
                             f'skill not in catalog: {missing}'))
    for ghost in sorted(set(listed) - set(present)):
        out.append(Violation('P14', 'catalog.json', 0,
                             f'catalog names a skill that is absent: {ghost}'))
    return out


def check_id_prefixes(root: Path) -> list[Violation]:
    """P16: entry-id prefixes must be unique across skills.

    The archive-side resolver keys entries by bare id. Two skills sharing a
    prefix therefore overwrite each other in a dict, and the loss is silent --
    the resolver reports a smaller total and still says "0 unresolved". Found
    the hard way when a settings skill and an ability-system skill both claimed
    GS, and nine entries vanished from the map without any check firing.
    """
    out: list[Violation] = []
    skills_dir = root / 'skills'
    if not skills_dir.is_dir():
        return out
    owners: dict[str, list[str]] = {}
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        fm = skill / 'references' / 'failure-modes.md'
        if not fm.is_file():
            continue
        for line in _read(fm).splitlines():
            m = re.match(r'^###\s+([A-Z]{2,4})-\d+\b', line)
            if m:
                owners.setdefault(m.group(1), [])
                if skill.name not in owners[m.group(1)]:
                    owners[m.group(1)].append(skill.name)
                break
    for prefix, skills in sorted(owners.items()):
        if len(skills) > 1:
            for name in skills:
                out.append(Violation(
                    'P16', f'skills/{name}/references/failure-modes.md', 0,
                    f'prefix {prefix} also used by: '
                    f'{", ".join(s for s in skills if s != name)}'))
    return out


def check_top_level(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for entry in sorted(root.iterdir()):
        if entry.name not in ALLOWED_TOP_LEVEL:
            out.append(Violation('P11', entry.name, 0,
                                 'not part of the plugin shipping surface'))
    return out


def check_junk(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for path in _shipped_files(root):
        rel = path.relative_to(root).as_posix()
        if path.suffix.lower() in JUNK_SUFFIXES or '__pycache__' in rel:
            out.append(Violation('P12', rel, 0, 'disallowed file type'))
    return out


def check_skills(root: Path) -> list[Violation]:
    out: list[Violation] = []
    skills_dir = root / 'skills'
    if not skills_dir.is_dir():
        return out
    for skill in sorted(p for p in skills_dir.iterdir() if p.is_dir()):
        rel = f'skills/{skill.name}/SKILL.md'
        md = skill / 'SKILL.md'
        if not md.is_file():
            out.append(Violation('P06', rel, 0, 'missing SKILL.md'))
            continue
        text = _read(md)
        front = _frontmatter(text)
        if front is None:
            out.append(Violation('P06', rel, 1, 'missing YAML frontmatter'))
            continue

        name = front.get('name', '')
        if not name:
            out.append(Violation('P06', rel, 1, 'no name field'))
        elif not RE_KEBAB.match(name):
            out.append(Violation('P06', rel, 1, f'name not kebab-case: {name}'))
        elif name != skill.name:
            out.append(Violation('P06', rel, 1,
                                 f'name {name} != folder {skill.name}'))

        desc = front.get('description', '').strip()
        if not desc or desc in ('>-', '>', '|'):
            out.append(Violation('P07', rel, 1, 'no description field'))

        fm = skill / 'references' / 'failure-modes.md'
        if not fm.is_file():
            out.append(Violation('P08', rel, 0,
                                 'missing references/failure-modes.md'))
        elif 'references/failure-modes.md' not in text:
            out.append(Violation('P08', rel, 0,
                                 'SKILL.md does not link failure-modes.md'))
        else:
            out.extend(check_entries(root, fm))

        out.extend(check_links(root, skill, md, text))
        refs_dir = skill / 'references'
        if refs_dir.is_dir():
            for ref in sorted(refs_dir.glob('*.md')):
                out.extend(check_links(root, skill, ref, _read(ref)))
    return out


def check_entries(root: Path, fm: Path) -> list[Violation]:
    """Every '### ' entry in failure-modes.md carries all required fields."""
    out: list[Violation] = []
    rel = fm.relative_to(root).as_posix()
    lines = _read(fm).splitlines()
    entries: list[tuple[int, str, list[str]]] = []
    cur = None
    for n, line in enumerate(lines, 1):
        m = RE_HEADING.match(line)
        if m and len(m.group(1)) == 3:
            cur = (n, m.group(2), [])
            entries.append(cur)
        elif cur is not None:
            fm_field = RE_ENTRY_FIELD.match(line)
            if fm_field:
                cur[2].append(fm_field.group(1).strip())
    if not entries:
        out.append(Violation('P09', rel, 0, 'no "### " entries found'))
        return out

    # P15: identifiers must run 01, 02, 03... in the order a reader meets them.
    # Reordering sections without renumbering leaves gaps that read as deleted
    # entries, and a stable id that moved is worse than one that never existed.
    # Caught twice by hand during authoring, hence a rule.
    seq = []
    for start, title, _ in entries:
        m = re.match(r'^([A-Z]{2,4})-(\d+)\b', title)
        if m:
            seq.append((start, m.group(1), int(m.group(2))))
    if seq:
        prefixes = {p for _, p, _ in seq}
        if len(prefixes) > 1:
            out.append(Violation('P15', rel, seq[0][0],
                                 f'mixed id prefixes: {sorted(prefixes)}'))
        for i, (start, prefix, num) in enumerate(seq, 1):
            if num != i:
                out.append(Violation(
                    'P15', rel, start,
                    f'{prefix}-{num:02d} is entry {i} in document order'))
                break
    for start, title, fields in entries:
        present = {f.lower() for f in fields}
        missing = [f for f in REQUIRED_ENTRY_FIELDS
                   if f.lower() not in present]
        if missing:
            out.append(Violation('P09', rel, start,
                                 f'{title}: missing {", ".join(missing)}'))
    return out


def check_links(root: Path, skill: Path, src: Path, text: str) -> list[Violation]:
    out: list[Violation] = []
    rel = src.relative_to(root).as_posix()
    skill_res = skill.resolve()
    for n, line in enumerate(text.splitlines(), 1):
        for target in RE_MD_LINK.findall(line):
            t = target.strip()
            if '://' in t or t.startswith('#') or t.startswith('mailto:'):
                continue
            clean = t.split('#', 1)[0]
            if not clean:
                continue
            dest = (src.parent / clean).resolve()
            try:
                dest.relative_to(skill_res)
            except ValueError:
                out.append(Violation('P10', rel, n,
                                     f'link escapes skill dir: {t}'))
                continue
            if not dest.exists():
                out.append(Violation('P10', rel, n, f'broken link: {t}'))
    return out


def check_manifest(root: Path) -> list[Violation]:
    out: list[Violation] = []
    mf = root / '.claude-plugin' / 'plugin.json'
    if not mf.is_file():
        out.append(Violation('P11', '.claude-plugin/plugin.json', 0,
                             'manifest missing'))
        return out
    try:
        data = json.loads(_read(mf))
    except json.JSONDecodeError as exc:
        out.append(Violation('P11', '.claude-plugin/plugin.json', 0,
                             f'invalid JSON: {exc}'))
        return out
    name = data.get('name', '')
    if not name or not RE_KEBAB.match(name):
        out.append(Violation('P11', '.claude-plugin/plugin.json', 0,
                             f'manifest name not kebab-case: {name!r}'))
    for entry in sorted((root / '.claude-plugin').iterdir()):
        if entry.name != 'plugin.json':
            out.append(Violation('P11', f'.claude-plugin/{entry.name}', 0,
                                 '.claude-plugin holds only the manifest'))
    return out


CHECKS = (check_text_rules, check_top_level, check_junk, check_skills,
          check_manifest, check_harness_neutral, check_engine_tool_surface,
          check_catalog,
          check_id_prefixes)


def run(root: Path) -> list[Violation]:
    out: list[Violation] = []
    for check in CHECKS:
        out.extend(check(root))
    return sorted(out, key=lambda v: (v.rule, v.path, v.line))


def main(argv: list[str]) -> int:
    if '--list-rules' in argv:
        for r in RULES:
            print(f'{r.id}  {r.what}')
        return 0
    args = [a for a in argv if not a.startswith('--')]
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parents[1]
    if not root.is_dir():
        print(f'ERROR: not a directory: {root}')
        return 2
    violations = run(root)
    for v in violations:
        loc = f'{v.path}:{v.line}' if v.line else v.path
        print(f'{v.rule}  {loc}  {v.text}')
    fired = sorted({v.rule for v in violations})
    print(f'\n{len(violations)} violations, '
          f'{len(fired)} of {len(RULES)} rules fired')
    if violations:
        print('rules fired: ' + ' '.join(fired))
    return 1 if violations else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
