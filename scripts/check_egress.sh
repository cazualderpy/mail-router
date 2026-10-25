#!/usr/bin/env bash
# Prüft, dass api und ollama zur Laufzeit KEIN Internet erreichen.
# Exit 0 nur, wenn beide scheitern. "Scheitern" heißt hier: Netzwerkfehler (nicht: fehlendes Binary).
cd "$(dirname "$0")/.." || exit 2

open=0

# api: HTTPS-Aufruf; nur ein URLError/OSError gilt als blockiert, alles andere (z. B. Exec-Fehler) nicht.
out=$(docker compose exec -T api python -c "
import sys, urllib.request, urllib.error
try:
    urllib.request.urlopen('https://example.com', timeout=5)
except (urllib.error.URLError, OSError) as e:
    print('network failure:', e); sys.exit(7)
print('reachable')
" 2>&1); rc=$?
echo "api:    rc=$rc $out"
if [ $rc -ne 7 ]; then open=1; fi

# ollama: TCP-Verbindung per bash /dev/tcp zu einer festen IP (kein DNS) und zusätzlich zum Namen.
for target in 1.1.1.1/443 registry.ollama.ai/443; do
  out=$(docker compose exec -T ollama bash -c "timeout 5 bash -c 'exec 3<>/dev/tcp/${target%/*}/${target#*/}' 2>&1; echo \"exit=\$?\"" 2>&1)
  echo "ollama: $target $out"
  # exit=0 -> verbunden; exit=1 -> Verbindung/DNS fehlgeschlagen (bash meldet Fehler); 124 -> Timeout
  case "$out" in
    *"exit=0"*) open=1 ;;
    *"exit=1"*|*"exit=124"*) ;;
    *) open=1 ;;
  esac
done

if [ $open -eq 0 ]; then echo "EGRESS BLOCKED"; exit 0; fi
echo "EGRESS OPEN"; exit 1
