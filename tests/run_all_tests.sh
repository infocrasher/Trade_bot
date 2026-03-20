#!/bin/bash
# tests/run_all_tests.sh
# Exécute tous les fichiers YAML tests du projet dynamiquement.

# Se placer à la racine du projet
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="$PYTHONPATH:$ROOT_DIR"
cd "$ROOT_DIR"

TOTAL_PASS=0
TOTAL_FAIL=0
EXIT_STATUS=0

echo "========================================"
echo "  RUNNING ALL TESTS"
echo "========================================"

# Trouver tous les fichiers test_*.py en excluant Fateh_bot, Sentinelle bot, FNewbot et venv
TEST_FILES=$(find . -name "test_*.py" -type f -not -path "./Fateh_bot/*" -not -path "./Sentinelle bot/*" -not -path "./FNewbot/*" -not -path "./venv/*" -not -name "test_agent1.py" -not -name "test_agent2.py" -not -name "test_structure.py" -not -name "test_structure3.py" -not -name "test_e2.py" | sort)

for file in $TEST_FILES; do
    echo "----------------------------------------"
    echo "Executing: $file"
    
    # Exécuter et capturer la sortie
    FILE_OUTPUT=$(python3 "$file" 2>&1)
    FILE_STATUS=$?
    
    # Afficher la sortie pour les logs
    echo "$FILE_OUTPUT"
    
    # Compter les PASS et FAIL dans la sortie (ignorer ❌ qui est utilisé par Elliott pour raison de fonction métier)
    FILE_PASS=$(echo "$FILE_OUTPUT" | grep -oE "PASS|PASSED|✅" | wc -l)
    FILE_FAIL=$(echo "$FILE_OUTPUT" | grep -oE "FAIL|FAILED" | wc -l)
    
    if [ $FILE_STATUS -ne 0 ]; then
        echo "⚠️  [ERREUR] $file a terminé avec un code d'erreur: $FILE_STATUS"
        EXIT_STATUS=1
        if [ $FILE_FAIL -eq 0 ]; then
            FILE_FAIL=1
        fi
    fi
    
    echo "-> Bilan pour $file : $FILE_PASS PASS / $FILE_FAIL FAIL"
    
    TOTAL_PASS=$((TOTAL_PASS + FILE_PASS))
    TOTAL_FAIL=$((TOTAL_FAIL + FILE_FAIL))
done

echo "========================================"
echo "TOTAL : $TOTAL_PASS tests passés"
if [ $TOTAL_FAIL -gt 0 ]; then
    echo "TOTAL : $TOTAL_FAIL tests échoués"
    exit 1
fi

if [ $EXIT_STATUS -ne 0 ]; then
    exit 1
fi

exit 0
