#!/bin/bash
# Assegna tutte le issue a giamma80

REPO="giamma80/profilebot"
ASSIGNEE="giamma80"

echo "Assegnando tutte le issue a $ASSIGNEE..."

# Ottieni tutte le issue aperte e assegnale
for ISSUE_NUM in $(gh issue list --repo $REPO --state open --json number -q '.[].number'); do
    echo "  Assegnando issue #$ISSUE_NUM..."
    gh issue edit $ISSUE_NUM --repo $REPO --add-assignee $ASSIGNEE 2>/dev/null
done

echo ""
echo "✅ Tutte le issue assegnate a $ASSIGNEE"
echo ""
echo "Verifica: https://github.com/$REPO/issues"
