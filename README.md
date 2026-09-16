# Guias Torrelodones: Management App

This is a minimal, single-process app to replace the manual Google Drive and paper approach AGT (Asociacion Guías de Torrelodones) currently uses to track its Kraal (group of adult volunteers), its ramas (groups of children separated by age) and meeting minutes across each year.

## Feature domains

1. **Kraal & Rama Management** (`src/kraal/`) — volunteers, directive roles,
   ramas, and rama assignments per ronda. Includes a continuity report that
   diffs two rondas' rosters (who joined, who left, who moved ramas).
2. **Meeting & Decision Log — Actas** (`src/actas/`) — structured meeting
   records: agenda items, decisions with vote results, and calendar events.