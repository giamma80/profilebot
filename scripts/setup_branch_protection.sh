#!/bin/bash
# Configura branch protection per main/master

REPO="giamma80/profilebot"
BRANCH="master"  # Cambia in "main" se necessario

echo "Configurando branch protection per $BRANCH..."

gh api \
  --method PUT \
  -H "Accept: application/vnd.github+json" \
  /repos/$REPO/branches/$BRANCH/protection \
  -f required_status_checks='{"strict":true,"contexts":["lint","test"]}' \
  -f enforce_admins=false \
  -f required_pull_request_reviews='{"required_approving_review_count":1}' \
  -f restrictions=null \
  -f allow_force_pushes=false \
  -f allow_deletions=false

echo ""
echo "✅ Branch protection configurata per $BRANCH"
echo ""
echo "Regole attive:"
echo "  - CI deve passare (lint + test)"
echo "  - 1 review richiesta per merge"
echo "  - No force push"
echo "  - No delete branch"
