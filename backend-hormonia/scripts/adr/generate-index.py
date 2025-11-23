#!/usr/bin/env python3
"""
ADR Index Generator

Automatically generates index table in README.md from ADR files.
"""

import re
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ADRMetadata:
    """Metadata extracted from an ADR file"""

    number: str
    title: str
    date: str
    status: str
    tags: List[str]
    filename: str


class ADRIndexGenerator:
    """Generates index of ADRs"""

    def __init__(self, adr_dir: Path):
        self.adr_dir = adr_dir
        self.adrs: List[ADRMetadata] = []

    def extract_metadata(self, adr_file: Path) -> ADRMetadata:
        """Extract metadata from ADR file"""
        content = adr_file.read_text()

        # Extract ADR number and title
        title_match = re.search(r"^# ADR-(\d{4}): (.+)$", content, re.MULTILINE)
        if not title_match:
            raise ValueError(f"Invalid ADR format in {adr_file.name}")

        number = title_match.group(1)
        title = title_match.group(2)

        # Extract status
        status_match = re.search(
            r"## Status\s+(.+?)\s+Date:", content, re.DOTALL
        )
        status = "Unknown"
        if status_match:
            status_lines = [
                line.strip()
                for line in status_match.group(1).split("\n")
                if line.strip()
            ]
            if status_lines:
                status = status_lines[0]

        # Extract date
        date_match = re.search(r"Date: (\d{4}-\d{2}-\d{2})", content)
        date = date_match.group(1) if date_match else "Unknown"

        # Extract tags
        tags_match = re.search(r"\*\*Tags\*\*: (.+)", content)
        tags = []
        if tags_match:
            tags = [tag.strip() for tag in tags_match.group(1).split(",")]

        return ADRMetadata(
            number=number,
            title=title,
            date=date,
            status=status,
            tags=tags,
            filename=adr_file.name,
        )

    def collect_adrs(self):
        """Collect all ADRs from directory"""
        adr_files = sorted(self.adr_dir.glob("ADR-*.md"))

        for adr_file in adr_files:
            # Skip template
            if adr_file.name == "ADR-0000-template.md":
                continue

            try:
                metadata = self.extract_metadata(adr_file)
                self.adrs.append(metadata)
            except Exception as e:
                print(f"⚠️  Warning: Could not parse {adr_file.name}: {e}")

    def generate_table(self) -> str:
        """Generate markdown table of ADRs"""
        lines = [
            "| ADR | Title | Date | Status | Tags |",
            "|-----|-------|------|--------|------|",
        ]

        for adr in self.adrs:
            tags_str = ", ".join(adr.tags) if adr.tags else "-"
            lines.append(
                f"| [ADR-{adr.number}](./{adr.filename}) | "
                f"{adr.title} | "
                f"{adr.date} | "
                f"{adr.status} | "
                f"{tags_str} |"
            )

        return "\n".join(lines)

    def categorize_adrs(self) -> Dict[str, List[ADRMetadata]]:
        """Categorize ADRs by tags"""
        categories = {
            "Backend & Infrastructure": [],
            "Security & Compliance": [],
            "Integration & External Services": [],
            "Development Process": [],
            "Architecture & Design": [],
        }

        for adr in self.adrs:
            # Categorize based on tags
            if any(tag in adr.tags for tag in ["backend", "database", "infrastructure"]):
                categories["Backend & Infrastructure"].append(adr)
            if any(tag in adr.tags for tag in ["security", "authentication", "compliance"]):
                categories["Security & Compliance"].append(adr)
            if any(tag in adr.tags for tag in ["integration", "external-api", "messaging"]):
                categories["Integration & External Services"].append(adr)
            if any(tag in adr.tags for tag in ["methodology", "process", "ai", "agents"]):
                categories["Development Process"].append(adr)
            if any(tag in adr.tags for tag in ["architecture", "design-patterns"]):
                categories["Architecture & Design"].append(adr)

        return categories

    def generate_categorized_list(self) -> str:
        """Generate categorized list of ADRs"""
        categories = self.categorize_adrs()
        lines = []

        for category, adrs in categories.items():
            if not adrs:
                continue

            lines.append(f"### {category}")
            for adr in adrs:
                lines.append(f"- ADR-{adr.number}: {adr.title}")
            lines.append("")

        return "\n".join(lines)

    def update_readme(self):
        """Update README.md with generated index"""
        readme_path = self.adr_dir / "README.md"

        if not readme_path.exists():
            print(f"❌ README.md not found at {readme_path}")
            return

        content = readme_path.read_text()

        # Generate new table
        new_table = self.generate_table()

        # Replace table in Active ADRs section
        pattern = (
            r"(### Active ADRs\s+)"
            r"\|.+?\|.+?\n"  # Header row
            r"\|[-|]+\|\n"  # Separator
            r"(?:\|.+?\|\n)*"  # Data rows
        )

        replacement = f"\\1{new_table}\n"
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)

        # Generate categorized list
        categorized_list = self.generate_categorized_list()

        # Replace categorized section
        cat_pattern = r"(## ADRs by Category\s+)(?:###.+?\n(?:-.+?\n)*\n*)+"
        cat_replacement = f"\\1\n{categorized_list}"
        new_content = re.sub(cat_pattern, cat_replacement, new_content, flags=re.MULTILINE)

        # Update last modified date
        today = datetime.now().strftime("%Y-%m-%d")
        new_content = re.sub(
            r"\*\*Last Updated\*\*: \d{4}-\d{2}-\d{2}",
            f"**Last Updated**: {today}",
            new_content,
        )

        # Write back
        readme_path.write_text(new_content)
        print(f"✅ Updated {readme_path}")


def main():
    """Main entry point"""
    adr_dir = Path("docs/architecture/decisions")

    if not adr_dir.exists():
        print(f"❌ ADR directory not found: {adr_dir}")
        return

    generator = ADRIndexGenerator(adr_dir)

    print("Collecting ADRs...")
    generator.collect_adrs()

    print(f"Found {len(generator.adrs)} ADR(s)")

    print("Generating index...")
    generator.update_readme()

    print("✅ Done!")


if __name__ == "__main__":
    main()
