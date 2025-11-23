#!/usr/bin/env python3
"""
ADR Validation Script

Validates that ADRs follow the correct format and include all required sections.
"""

import re
import sys
from pathlib import Path
from typing import List, Tuple


class ADRValidator:
    """Validates Architecture Decision Records"""

    REQUIRED_SECTIONS = [
        "Status",
        "Context",
        "Decision",
        "Consequences",
        "Alternatives Considered",
        "References",
        "Metadata",
    ]

    VALID_STATUSES = ["Proposed", "Accepted", "Rejected", "Superseded", "Deprecated"]

    def __init__(self, adr_path: Path):
        self.adr_path = adr_path
        self.content = adr_path.read_text()
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def validate(self) -> Tuple[bool, List[str], List[str]]:
        """
        Validate ADR and return (is_valid, errors, warnings)
        """
        self._validate_filename()
        self._validate_title()
        self._validate_status()
        self._validate_required_sections()
        self._validate_metadata()
        self._validate_references()
        self._check_completeness()

        is_valid = len(self.errors) == 0
        return is_valid, self.errors, self.warnings

    def _validate_filename(self):
        """Validate ADR filename format"""
        filename = self.adr_path.name

        # Template is exempt from validation
        if filename == "ADR-0000-template.md":
            return

        # Check format: ADR-XXXX-title.md
        if not re.match(r"ADR-\d{4}-[\w-]+\.md$", filename):
            self.errors.append(
                f"Invalid filename format: {filename}. "
                "Expected: ADR-XXXX-title.md"
            )

    def _validate_title(self):
        """Validate ADR has proper title"""
        # Find first heading
        title_match = re.search(r"^# ADR-\d{4}: (.+)$", self.content, re.MULTILINE)

        if not title_match:
            self.errors.append("ADR must start with '# ADR-XXXX: Title'")
        else:
            title = title_match.group(1)
            if len(title) < 5:
                self.warnings.append("Title seems too short")
            if len(title) > 100:
                self.warnings.append("Title seems too long (>100 chars)")

    def _validate_status(self):
        """Validate status section"""
        status_match = re.search(
            r"## Status\s+(.+?)\s+Date:", self.content, re.DOTALL
        )

        if not status_match:
            self.errors.append("Missing or invalid Status section")
            return

        status = status_match.group(1).strip()
        status_lines = [line.strip() for line in status.split("\n") if line.strip()]

        if not status_lines:
            self.errors.append("Status section is empty")
            return

        # First non-empty line should be a valid status
        first_status = status_lines[0]
        if first_status not in self.VALID_STATUSES:
            self.errors.append(
                f"Invalid status: '{first_status}'. "
                f"Must be one of: {', '.join(self.VALID_STATUSES)}"
            )

        # Check for date
        date_match = re.search(r"Date: (\d{4}-\d{2}-\d{2})", self.content)
        if not date_match:
            self.errors.append("Missing date in Status section (format: YYYY-MM-DD)")

    def _validate_required_sections(self):
        """Validate all required sections are present"""
        for section in self.REQUIRED_SECTIONS:
            section_pattern = f"## {section}"
            if section_pattern not in self.content:
                self.errors.append(f"Missing required section: {section}")

    def _validate_metadata(self):
        """Validate metadata section"""
        metadata_match = re.search(r"## Metadata(.+?)$", self.content, re.DOTALL)

        if not metadata_match:
            return  # Already caught by required sections check

        metadata = metadata_match.group(1)

        required_meta = ["Author", "Reviewers", "Last Updated", "Tags"]
        for meta in required_meta:
            if f"**{meta}**:" not in metadata:
                self.warnings.append(f"Missing metadata field: {meta}")

    def _validate_references(self):
        """Validate references section"""
        references_match = re.search(r"## References(.+?)## ", self.content, re.DOTALL)

        if not references_match:
            self.warnings.append("References section appears empty")
            return

        references = references_match.group(1)

        # Check for at least one link
        if not re.search(r"\[.+?\]\(.+?\)", references):
            self.warnings.append("References section should include links")

    def _check_completeness(self):
        """Check for placeholder text that should be replaced"""
        placeholders = [
            r"\[.*?\]",  # [Placeholder text]
            r"YYYY-MM-DD",
            r"XXXX",
            r"\.\.\.",  # Ellipsis
        ]

        for placeholder in placeholders:
            matches = re.findall(placeholder, self.content)
            if matches:
                # Filter out valid markdown links
                invalid_matches = [
                    m for m in matches if not (m.startswith("[") and "](" in m)
                ]
                if invalid_matches:
                    self.warnings.append(
                        f"Found {len(invalid_matches)} placeholder(s) "
                        "that should be replaced"
                    )
                    break

        # Check section content length
        for section in ["Context", "Decision", "Consequences"]:
            section_match = re.search(
                f"## {section}(.+?)## ", self.content, re.DOTALL
            )
            if section_match:
                content = section_match.group(1).strip()
                if len(content) < 100:
                    self.warnings.append(
                        f"{section} section seems incomplete (<100 chars)"
                    )


def validate_all_adrs(adr_dir: Path) -> int:
    """Validate all ADRs in directory"""
    adr_files = sorted(adr_dir.glob("ADR-*.md"))

    if not adr_files:
        print("❌ No ADR files found")
        return 1

    print(f"Validating {len(adr_files)} ADR(s)...\n")

    total_errors = 0
    total_warnings = 0

    for adr_file in adr_files:
        # Skip template
        if adr_file.name == "ADR-0000-template.md":
            print(f"⏭️  Skipping template: {adr_file.name}")
            continue

        validator = ADRValidator(adr_file)
        is_valid, errors, warnings = validator.validate()

        if is_valid and not warnings:
            print(f"✅ {adr_file.name}")
        elif is_valid and warnings:
            print(f"⚠️  {adr_file.name}")
            for warning in warnings:
                print(f"    ⚠️  {warning}")
            total_warnings += len(warnings)
        else:
            print(f"❌ {adr_file.name}")
            for error in errors:
                print(f"    ❌ {error}")
            for warning in warnings:
                print(f"    ⚠️  {warning}")
            total_errors += len(errors)
            total_warnings += len(warnings)

        print()

    # Summary
    print("=" * 60)
    print(f"Total ADRs validated: {len(adr_files) - 1}")  # Exclude template
    print(f"Errors: {total_errors}")
    print(f"Warnings: {total_warnings}")

    if total_errors > 0:
        print("\n❌ Validation failed")
        return 1
    elif total_warnings > 0:
        print("\n⚠️  Validation passed with warnings")
        return 0
    else:
        print("\n✅ All ADRs are valid")
        return 0


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        # Validate specific file
        adr_path = Path(sys.argv[1])
        if not adr_path.exists():
            print(f"❌ File not found: {adr_path}")
            sys.exit(1)

        validator = ADRValidator(adr_path)
        is_valid, errors, warnings = validator.validate()

        print(f"Validating: {adr_path.name}\n")

        for error in errors:
            print(f"❌ {error}")

        for warning in warnings:
            print(f"⚠️  {warning}")

        if is_valid:
            print(f"\n✅ ADR is valid")
            sys.exit(0 if not warnings else 0)
        else:
            print(f"\n❌ ADR validation failed")
            sys.exit(1)
    else:
        # Validate all ADRs
        adr_dir = Path("docs/architecture/decisions")
        if not adr_dir.exists():
            print(f"❌ ADR directory not found: {adr_dir}")
            sys.exit(1)

        exit_code = validate_all_adrs(adr_dir)
        sys.exit(exit_code)


if __name__ == "__main__":
    main()
