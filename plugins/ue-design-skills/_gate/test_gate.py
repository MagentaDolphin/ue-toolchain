"""Poisoned-fixture corpus for the delivery gate.

    python _gate/test_gate.py

Every rule in gate.RULES must have exactly one poison here, and that poison must
make its rule fire. A rule that never reddens on a fixture does not exist -- the
previous validator in this project ran "successfully" for months while checking
a literal that could not occur. This file is the answer to that.

The clean baseline lives in _gate/fixtures/clean and must be green. Each variant
is that tree copied to a temp directory plus exactly one mutation.

Output is ASCII only; the Cyrillic poison is written as escapes and never
printed.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gate  # noqa: E402

CLEAN = Path(__file__).resolve().parent / 'fixtures' / 'clean'
SKILL = 'skills/sample-skill/SKILL.md'
FM = 'skills/sample-skill/references/failure-modes.md'

# rule id -> (operation, path, payload, replacement)
POISONS: dict[str, tuple] = {
    'P01': ('append', SKILL,
            '\nDonor tree lives at D:\\Work\\Donor\\tree on the build box.\n'),
    'P02': ('append', SKILL,
            '\nSee RangedWeaponInstance.cpp:194 for the original.\n'),
    'P03': ('append', SKILL,
            '\nThe donor project Lyra shipped this pattern unchanged.\n'),
    'P04': ('append', SKILL,
            '\n\u041f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u0435.\n'),
    'P05': ('append', SKILL, '\nRelated: [[ue-modular-gameplay]]\n'),
    'P06': ('replace', SKILL, 'name: sample-skill', 'name: renamed-skill'),
    'P07': ('replace', SKILL, 'description: >-', 'summary: >-'),
    'P08': ('delete', FM),
    'P09': ('replace', FM, '**Guardrail.**', 'Guardrail:'),
    'P10': ('append', SKILL,
            '\nSee [the archive](../../../notes/00-index.md).\n'),
    'P11': ('mkfile', 'notes/leak.md', '# a note from the archive\n'),
    'P12': ('mkfile', 'skills/sample-skill/references/stale.pyc', 'junk\n'),
    'P13': ('append', SKILL,
            '\nRun this through Claude Code with ${CLAUDE_PLUGIN_ROOT} set.\n'),
    'P14': ('delete', 'catalog.json'),
    # The single clean entry is SS-01 and sits first. Renaming it to SS-02
    # leaves position 1 holding number 02, which is exactly the gap that
    # reordering sections during authoring produces.
    'P15': ('replace', FM, '### SS-01', '### SS-02'),
    # A second skill reusing the SS- prefix. This is the defect that let nine
    # shipped entries vanish from the archive resolver without any count
    # disagreeing loudly enough to notice.
    'P16': ('copyskill', 'skills/sample-skill', 'sample-twin'),
    # The engine's own agent-tool layer is Experimental and its surface moves
    # between builds: one measured session exposed 53 toolsets, and the count
    # of visible tools flips between 3 and hundreds on a single project
    # setting. A recipe naming a toolset does not error on the next build, it
    # finds nothing -- which reads as "no problem here".
    'P17': ('append', FM,
            '\nRun this through the EditorAppToolset via call_tool at '
            'localhost:8000.\n'),
}


# Surface coverage is a separate question from rule coverage. POISONS proves
# each rule can fire; this proves each file the gate CLAIMS to scan actually
# reaches the line-level rules. Both were needed: every rule above had a
# working fixture while a LICENSE carrying all five text violations passed
# green, because the fixtures all poison .md and LICENSE has no extension.
# Declaring a file on the surface and filtering it out one line later is the
# same defect class as a rule with no fixture -- coverage asserted, not had.
SURFACE_POISON = (
    'Donor tree at D:\\Work\\Donor\\tree\n'
    'See RangedWeaponInstance.cpp:194\n'
    'The donor project Lyra shipped this\n'
    '\u041f\u0440\u0438\u043c\u0435\u0447\u0430\u043d\u0438\u0435\n'
    'Related: [[ue-modular-gameplay]]\n')
SURFACE_EXPECT = {'P01', 'P02', 'P03', 'P04', 'P05'}


def check_surface(failures: list[str]) -> None:
    """Every name in gate.SCAN_ROOT_FILES must reach the line-level rules."""
    for name in gate.SCAN_ROOT_FILES:
        with tempfile.TemporaryDirectory() as td:
            root = materialize(Path(td) / 'surface')
            (root / name).write_text(SURFACE_POISON, encoding='utf-8')
            fired = {v.rule for v in gate.run(root) if v.path == name}
            missing = SURFACE_EXPECT - fired
            print(f'surface {name:<12} '
                  f'{"scanned" if not missing else "NOT SCANNED"}')
            if missing:
                failures.append(
                    f'{name} is on the scan surface but line rules '
                    f'{sorted(missing)} never saw it')


def materialize(tmp: Path) -> Path:
    root = tmp / 'plugin'
    shutil.copytree(CLEAN, root)
    return root


def poison(root: Path, spec: tuple) -> None:
    op = spec[0]
    target = root / spec[1]
    if op == 'append':
        target.write_text(
            target.read_text(encoding='utf-8') + spec[2], encoding='utf-8')
    elif op == 'replace':
        text = target.read_text(encoding='utf-8')
        if spec[2] not in text:
            raise AssertionError(f'poison anchor absent: {spec[2]!r}')
        target.write_text(text.replace(spec[2], spec[3], 1), encoding='utf-8')
    elif op == 'delete':
        target.unlink()
    elif op == 'mkfile':
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(spec[2], encoding='utf-8')
    elif op == 'copyskill':
        # Duplicate a skill under a new folder name, keeping its entry-id
        # prefix. The frontmatter name and the catalog entry are fixed up so
        # that P06 and P14 stay green and only the prefix collision fires.
        src, dst = root / spec[1], root / spec[1].rsplit('/', 1)[0] / spec[2]
        shutil.copytree(src, dst)
        md = dst / 'SKILL.md'
        md.write_text(
            md.read_text(encoding='utf-8').replace(
                f'name: {src.name}', f'name: {spec[2]}'), encoding='utf-8')
        cat = root / 'catalog.json'
        data = json.loads(cat.read_text(encoding='utf-8'))
        twin = dict(data['skills'][0])
        twin['id'] = spec[2]
        twin['path'] = f'skills/{spec[2]}'
        twin['entry'] = f'skills/{spec[2]}/SKILL.md'
        twin['references'] = [r.replace(src.name, spec[2])
                              for r in twin.get('references', [])]
        data['skills'].append(twin)
        cat.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    else:
        raise AssertionError(f'unknown poison op: {op}')


def main() -> int:
    failures: list[str] = []
    rule_ids = {r.id for r in gate.RULES}

    missing = rule_ids - set(POISONS)
    extra = set(POISONS) - rule_ids
    if missing:
        failures.append(f'rules with no fixture: {sorted(missing)}')
    if extra:
        failures.append(f'fixtures for unknown rules: {sorted(extra)}')

    with tempfile.TemporaryDirectory() as td:
        root = materialize(Path(td) / 'clean')
        found = gate.run(root)
        if found:
            failures.append('clean baseline is not green:')
            for v in found:
                failures.append(f'    {v.rule} {v.path}:{v.line} {v.text}')
        else:
            print('clean baseline          green')

    for rule in sorted(POISONS):
        with tempfile.TemporaryDirectory() as td:
            root = materialize(Path(td) / rule)
            poison(root, POISONS[rule])
            fired = sorted({v.rule for v in gate.run(root)})
            ok = rule in fired
            others = [f for f in fired if f != rule]
            note = f'  (also {" ".join(others)})' if others else ''
            print(f'{rule} poison               '
                  f'{"fires" if ok else "SILENT"}{note}')
            if not ok:
                failures.append(
                    f'{rule}: poison did not fire the rule; fired={fired}')

    check_surface(failures)

    print()
    if failures:
        for f in failures:
            print('FAIL: ' + f)
        return 1
    print(f'{len(POISONS)} rules, each reddens on its own fixture, '
          f'{len(gate.SCAN_ROOT_FILES)} root files reach the line rules, '
          'baseline clean')
    return 0


if __name__ == '__main__':
    sys.exit(main())
