#!/bin/bash

# Create new ADR from template
# Usage: ./scripts/adr/new-adr.sh "Your Decision Title"

set -e

# Check arguments
if [ $# -eq 0 ]; then
    echo "❌ Error: ADR title required"
    echo "Usage: $0 \"Your Decision Title\""
    exit 1
fi

TITLE="$1"
ADR_DIR="docs/architecture/decisions"
TEMPLATE="$ADR_DIR/ADR-0000-template.md"

# Find next ADR number
LAST_ADR=$(ls -1 "$ADR_DIR"/ADR-[0-9]*.md 2>/dev/null | \
           grep -v "ADR-0000-template.md" | \
           sort -V | \
           tail -1 | \
           sed 's/.*ADR-\([0-9]*\)-.*/\1/')

if [ -z "$LAST_ADR" ]; then
    NEXT_NUM=1
else
    NEXT_NUM=$((10#$LAST_ADR + 1))
fi

# Format number with leading zeros (e.g., 0011)
NEXT_NUM_FORMATTED=$(printf "%04d" $NEXT_NUM)

# Create filename from title (lowercase, replace spaces with hyphens)
FILENAME=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | sed 's/[^a-z0-9-]//g')
NEW_ADR_FILE="$ADR_DIR/ADR-$NEXT_NUM_FORMATTED-$FILENAME.md"

# Check if file already exists
if [ -f "$NEW_ADR_FILE" ]; then
    echo "❌ Error: ADR file already exists: $NEW_ADR_FILE"
    exit 1
fi

# Copy template and replace placeholders
cp "$TEMPLATE" "$NEW_ADR_FILE"

# Get current date
CURRENT_DATE=$(date +%Y-%m-%d)

# Replace placeholders
sed -i "s/ADR-XXXX:/ADR-$NEXT_NUM_FORMATTED:/" "$NEW_ADR_FILE"
sed -i "s/\[Short Title of Decision\]/$TITLE/" "$NEW_ADR_FILE"
sed -i "s/YYYY-MM-DD/$CURRENT_DATE/" "$NEW_ADR_FILE"
sed -i "s/\[Proposed | Accepted | Rejected | Superseded | Deprecated\]/Proposed/" "$NEW_ADR_FILE"

echo "✅ Created new ADR: $NEW_ADR_FILE"
echo ""
echo "Next steps:"
echo "1. Edit the ADR and fill in all sections"
echo "2. Review with team and stakeholders"
echo "3. Update status to 'Accepted' when approved"
echo "4. Add to index in $ADR_DIR/README.md"
echo ""
echo "Opening in default editor..."

# Open in editor (try VSCode, then vim, then nano)
if command -v code &> /dev/null; then
    code "$NEW_ADR_FILE"
elif command -v vim &> /dev/null; then
    vim "$NEW_ADR_FILE"
elif command -v nano &> /dev/null; then
    nano "$NEW_ADR_FILE"
else
    echo "⚠️  No editor found. Please open manually: $NEW_ADR_FILE"
fi
