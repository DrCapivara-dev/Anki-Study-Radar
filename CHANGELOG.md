# Changelog

All notable changes to **Anki Study Radar** will be documented here.

## [0.2.0] - 2026-09-03

### Added
- Friendly graphical settings window.
- **Tools → Study Radar Settings...** menu shortcut.
- **⚙ Settings** button directly inside the Radar.
- Editable review intervals with spin boxes instead of manual JSON editing.
- Friendly controls for history window, maximum displayed decks, minimum session size and upcoming-review window.
- **Restore defaults** button.

### Changed
- The configuration can now be managed without editing JSON manually.
- The thematic interval ceiling now supports longer user-defined intervals (up to 730 days).

## [0.1.1] - 2026-09-02

### Changed
- Nested deck names are now displayed with a cleaner visual separator (`›`) instead of Anki's internal `::` separator.
- Internal Anki deck structure remains unchanged.

## [0.1.0] - 2026-09-01

### Added
- Initial beta release.
- Automatic discovery of decks from the user's collection.
- Thematic review recommendations based on meaningful study sessions.
- Progressive default intervals: 2, 4, 7, 14, 21, 30, 45 and 60 days.
- Performance adjustment using Again/Hard/Easy rates.
- Due, overdue, tomorrow and upcoming states.
- Configurable history window, row limit, minimum session size and upcoming window.
- Button to open a recommended deck.
- No modification of FSRS or card scheduling.
