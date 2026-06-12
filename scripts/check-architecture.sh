#!/usr/bin/env bash
# check-architecture.sh -- Verify monorepo boundary separation.
#
# Usage: bash scripts/check-architecture.sh
set -euo pipefail

echo "=== Monorepo Boundary Checks ==="
echo ""

VIOLATIONS=0

# Check 1: Ensure backend never imports Next.js/React or JS/TS dependencies
echo "Checking backend for frontend imports..."
backend_frontend_imports=$(grep -rnw "backend/app" -e "import react" -e "from react" -e "import next" 2>/dev/null || true)
if [ -n "$backend_frontend_imports" ]; then
  echo "  FAIL: Found frontend references in backend:"
  echo "$backend_frontend_imports"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo "  PASS: No frontend imports in backend"
fi

# Check 2: Ensure frontend never imports backend python modules or raw SQLAlchemy models
echo "Checking frontend for backend imports..."
frontend_backend_imports=$(grep -rnw "frontend/src" -e "import .* from '.*backend.*'" -e "import .* from '.*SQLAlchemy.*'" 2>/dev/null || true)
if [ -n "$frontend_backend_imports" ]; then
  echo "  FAIL: Found backend references in frontend:"
  echo "$frontend_backend_imports"
  VIOLATIONS=$((VIOLATIONS + 1))
else
  echo "  PASS: No backend imports in frontend"
fi

# Check 3: Check database connection leak patterns in backend (e.g. creating session without closing)
echo "Checking backend for unmanaged DB sessions..."
# Simple check: make sure SessionLocal is not used in global modules without proper context managers or Depends(get_db)
unmanaged_sessions=$(grep -rnw "backend/app/api" -e "SessionLocal()" 2>/dev/null || true)
if [ -n "$unmanaged_sessions" ]; then
  echo "  WARNING: Found direct SessionLocal usage in API router, recommend using get_db dependency:"
  echo "$unmanaged_sessions"
else
  echo "  PASS: Database sessions managed correctly in API layers"
fi

echo ""
echo "=== Summary ==="
if [ "$VIOLATIONS" -eq 0 ]; then
  echo "PASS: All architecture boundary checks passed"
  exit 0
else
  echo "FAIL: $VIOLATIONS architectural boundary violation(s) found"
  exit 1
fi
