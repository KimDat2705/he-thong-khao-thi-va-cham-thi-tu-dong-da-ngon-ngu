#!/usr/bin/env bash
# benchmark.sh -- Benchmark performance of question generation and scaling.
#
# Usage: bash scripts/benchmark.sh
set -euo pipefail

echo "=== Performance & Scaling Benchmark Suite ==="
echo ""

START_TIME=$(python3 -c "import time; print(time.time())" 2>/dev/null || date +%s)

# Run scale spec tests in pytest
echo "Running scaling performance test cases..."
cd backend
python -m pytest tests/test_specs_scale.py -v --tb=short

END_TIME=$(python3 -c "import time; print(time.time())" 2>/dev/null || date +%s)
DURATION=$(( (END_TIME - START_TIME) ))

echo ""
echo "Benchmark completed in ${DURATION}s."
echo "ALL PERFORMANCE TESTS PASSED"
exit 0
