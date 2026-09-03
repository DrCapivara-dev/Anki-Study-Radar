# Anki Study Radar v1.1.1

## Hotfix — Analytics / PyQt 6.9

This release fixes the crash that could appear when opening **Analytics → Desempenho**, specifically while drawing the weekly retention chart on Anki 25.09.x with PyQt 6.9.

### Fixed
- `QPainter.drawLine()` now receives `QPointF` geometry instead of raw floating-point coordinates.
- Chart baseline rendering was updated with the same Qt-safe approach.
- The Analytics Pro dashboard otherwise remains unchanged from v1.1.0.

### Unchanged
- Radar recommendations
- Smart Review / Quick Review
- Focus Session
- temporary filtered-deck cleanup
- OWNER / TESTER / PRO licensing
- FSRS-safe preview behavior

Install over the previous version and restart Anki.
