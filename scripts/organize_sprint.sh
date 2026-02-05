#!/bin/bash
# Script per organizzare le issue negli Sprint

# Ottieni il Project ID
PROJECT_ID=$(gh project list --owner giamma80 --format json | jq -r '.projects[] | select(.title=="ProfileBot MVP") | .number')
echo "Project ID: $PROJECT_ID"

# Sposta le issue dello Sprint 1 in "Sprint Current"
echo "Spostando issue Sprint 1 in 'Sprint Current'..."

# US-001, US-002, US-003 (issue #6, #7, #8)
for ISSUE in 6 7 8; do
    gh project item-edit --project-id $PROJECT_ID --id $(gh project item-list $PROJECT_ID --owner giamma80 --format json | jq -r ".items[] | select(.content.number==$ISSUE) | .id") --field-id $(gh project field-list $PROJECT_ID --owner giamma80 --format json | jq -r '.fields[] | select(.name=="Status") | .id') --single-select-option-id $(gh project field-list $PROJECT_ID --owner giamma80 --format json | jq -r '.fields[] | select(.name=="Status") | .options[] | select(.name=="Sprint Current") | .id') 2>/dev/null
    echo "  Issue #$ISSUE spostata"
done

echo ""
echo "Done! Verifica su: https://github.com/users/giamma80/projects/2"
