#!/bin/bash
# Script per configurare GitHub Project e Milestones
# Esegui con: ./scripts/setup_github_project.sh

REPO="giamma80/profilebot"

echo "🚀 Configurazione GitHub Project per ProfileBot..."
echo ""

# 1. Crea Milestones per ogni Sprint
echo "📅 Creazione Milestones..."

gh api repos/$REPO/milestones -f title="Sprint 1 - Setup" -f description="Infrastructure setup: Repository, Qdrant, Parser CV" -f due_on="2026-02-19T23:59:59Z"
gh api repos/$REPO/milestones -f title="Sprint 2 - Ingestion" -f description="Document ingestion: Skill extraction, Embedding pipeline" -f due_on="2026-03-05T23:59:59Z"
gh api repos/$REPO/milestones -f title="Sprint 3 - Search" -f description="Search & Matching: API ricerca, Filtro disponibilità" -f due_on="2026-03-19T23:59:59Z"
gh api repos/$REPO/milestones -f title="Sprint 4 - Matching" -f description="Advanced Matching: Job description match, LLM engine" -f due_on="2026-04-02T23:59:59Z"
gh api repos/$REPO/milestones -f title="Sprint 5 - UI" -f description="User Interface: Chat interface, Visualizzazione profili" -f due_on="2026-04-16T23:59:59Z"

echo "✅ Milestones creati!"
echo ""

# 2. Crea GitHub Project (v2)
echo "📋 Creazione Project Board..."

# Nota: gh project create richiede --owner per org/user
PROJECT_URL=$(gh project create --owner giamma80 --title "ProfileBot MVP" --format json | jq -r '.url' 2>/dev/null)

if [ -z "$PROJECT_URL" ]; then
    echo "⚠️  Project potrebbe già esistere o errore nella creazione."
    echo "   Crealo manualmente: https://github.com/users/giamma80/projects/new"
else
    echo "✅ Project creato: $PROJECT_URL"
fi

echo ""

# 3. Assegna issue alle milestone
echo "🔗 Assegnazione issue alle Milestones..."

# Ottieni i numeri delle milestone
SPRINT1=$(gh api repos/$REPO/milestones --jq '.[] | select(.title | contains("Sprint 1")) | .number')
SPRINT2=$(gh api repos/$REPO/milestones --jq '.[] | select(.title | contains("Sprint 2")) | .number')
SPRINT3=$(gh api repos/$REPO/milestones --jq '.[] | select(.title | contains("Sprint 3")) | .number')
SPRINT4=$(gh api repos/$REPO/milestones --jq '.[] | select(.title | contains("Sprint 4")) | .number')
SPRINT5=$(gh api repos/$REPO/milestones --jq '.[] | select(.title | contains("Sprint 5")) | .number')

echo "Sprint Milestones: S1=$SPRINT1, S2=$SPRINT2, S3=$SPRINT3, S4=$SPRINT4, S5=$SPRINT5"

# Sprint 1: US-001, US-002, US-003
for issue in $(gh issue list -R $REPO --label "sprint-1" --json number --jq '.[].number'); do
    gh issue edit $issue -R $REPO --milestone "Sprint 1 - Setup"
    echo "  → Issue #$issue → Sprint 1"
done

# Sprint 2: US-004, US-005
for issue in $(gh issue list -R $REPO --label "sprint-2" --json number --jq '.[].number'); do
    gh issue edit $issue -R $REPO --milestone "Sprint 2 - Ingestion"
    echo "  → Issue #$issue → Sprint 2"
done

# Sprint 3: US-006, US-007
for issue in $(gh issue list -R $REPO --label "sprint-3" --json number --jq '.[].number'); do
    gh issue edit $issue -R $REPO --milestone "Sprint 3 - Search"
    echo "  → Issue #$issue → Sprint 3"
done

# Sprint 4: US-008, US-009
for issue in $(gh issue list -R $REPO --label "sprint-4" --json number --jq '.[].number'); do
    gh issue edit $issue -R $REPO --milestone "Sprint 4 - Matching"
    echo "  → Issue #$issue → Sprint 4"
done

# Sprint 5: US-010, US-011, US-012
for issue in $(gh issue list -R $REPO --label "sprint-5" --json number --jq '.[].number'); do
    gh issue edit $issue -R $REPO --milestone "Sprint 5 - UI"
    echo "  → Issue #$issue → Sprint 5"
done

echo ""
echo "✅ Issue assegnate alle Milestones!"
echo ""

# 4. Riepilogo
echo "📊 Riepilogo Setup:"
echo ""
echo "Repository: https://github.com/$REPO"
echo "Issues: https://github.com/$REPO/issues"
echo "Milestones: https://github.com/$REPO/milestones"
echo ""
echo "🎯 Prossimi passi:"
echo "1. Vai su https://github.com/users/giamma80/projects"
echo "2. Apri il project 'ProfileBot MVP'"
echo "3. Aggiungi le issue al board (+ Add item → Repository → profilebot)"
echo "4. Configura le colonne: Backlog | Sprint Current | In Progress | Review | Done"
echo ""
echo "🚀 Buon lavoro con ProfileBot!"
