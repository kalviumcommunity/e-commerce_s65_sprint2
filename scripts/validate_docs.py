"""Validate the Sprint 2 documentation using only the Python standard library."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    ROOT / "README.md",
    ROOT / "PRD.md",
    ROOT / "docs" / "sprint-2-plan.md",
    ROOT / "docs" / "architecture.md",
    ROOT / "docs" / "decisions" / "0001-grounded-rag-architecture.md",
)


def validate_required_files() -> list[str]:
    return [f"Missing required file: {path.relative_to(ROOT)}" for path in REQUIRED_FILES if not path.is_file()]


def validate_module_coverage(plan: str) -> list[str]:
    errors: list[str] = []
    for module in range(1, 51):
        value = f"3.{module}"
        if value not in plan:
            errors.append(f"Sprint plan does not reference module {value}")
    return errors


def validate_required_sections(plan: str, architecture: str) -> list[str]:
    errors: list[str] = []
    plan_sections = (
        "Problem and intended outcome",
        "Target users",
        "Team responsibilities",
        "Milestones and dates",
        "Definition of done",
    )
    architecture_sections = (
        "Offline ingestion flow",
        "Online query flow",
        "Core contracts",
        "Grounding and safety controls",
        "Failure handling",
    )
    errors.extend(f"Sprint plan is missing section: {section}" for section in plan_sections if section not in plan)
    errors.extend(
        f"Architecture document is missing section: {section}"
        for section in architecture_sections
        if section not in architecture
    )
    return errors


def validate_relative_links() -> list[str]:
    errors: list[str] = []
    link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for document in REQUIRED_FILES:
        if not document.is_file():
            continue
        for target in link_pattern.findall(document.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            relative_target = target.split("#", 1)[0]
            if relative_target and not (document.parent / relative_target).resolve().exists():
                errors.append(
                    f"Broken relative link in {document.relative_to(ROOT)}: {target}"
                )
    return errors


def main() -> int:
    errors = validate_required_files()
    if not errors:
        plan = (ROOT / "docs" / "sprint-2-plan.md").read_text(encoding="utf-8")
        architecture = (ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
        errors.extend(validate_module_coverage(plan))
        errors.extend(validate_required_sections(plan, architecture))
        errors.extend(validate_relative_links())

    if errors:
        print("Documentation validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Documentation validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
