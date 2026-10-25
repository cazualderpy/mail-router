# Projektregeln für Agenten

- Lokaler MVZ-Posteingangs-Router. Maßgeblich: `docs/superpowers/specs/2026-10-25-mail-router-design.md`.
- Nur synthetische Daten. Mailadressen und Domains ausschließlich `*.example`.
- Keine Netz- oder Cloud-Aufrufe zur Laufzeit. Downloads nur im Setup-Schritt.
- Der Holdout liegt außerhalb des Repos und ist für bauende Agenten tabu (per `.claude/settings.json`
  gesperrt). Nicht suchen, nicht lesen, nicht nachbauen.
- Keine absoluten Home-Pfade und keine echten Personennamen in Dateien oder Commits.
  Einige Begriffe sind gesperrt; der Orchestrator prüft das vor dem Push.
- Ein Commit pro Plan-Task. Jede Commit-Nachricht endet mit
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Python mit `uv`, Tests mit `pytest`.
