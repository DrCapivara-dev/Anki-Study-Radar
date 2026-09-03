# 🧠 Anki Study Radar

**Anki Study Radar** is an add-on for Anki Desktop that analyzes your local review history and shows, directly on the deck screen, **which decks/topics may be worth revisiting today**.

> Current version: **v0.3.0 (beta)**

## Why this exists

Anki/FSRS is excellent at deciding when an **individual card** should reappear. Study Radar adds a different layer: it helps answer **“which topic/deck should I revisit today?”**.

For example, if you studied a deck two days ago and struggled with many cards, Study Radar may recommend revisiting that deck sooner. If repeated sessions go well, the thematic review interval gradually expands.

## Features

- Reads the user's **actual deck names automatically** — no predefined subjects.
- Supports nested Anki decks and displays them cleanly, e.g. `Medicine › Psychiatry › Psychosis` instead of `Medicine::Psychiatry::Psychosis`.
- Uses recent review history and the proportions of **Again / Hard / Good / Easy** answers.
- Ignores very small sessions so opening a deck and answering only a few cards does not necessarily reset the thematic review.
- Shows recommendations such as **Review today**, **Overdue**, **Tomorrow**, and **Coming soon**.
- Includes **Open** and **⚡ Quick Review** actions for recommended decks.
- **Quick Review** automatically selects difficult cards using recent Again/Hard answers and lapse history, then creates a short preview filtered deck.
- Shows a simple **priority score (1–100)** for each recommendation.
- Quick Review uses Anki's filtered-deck **preview mode**, so it does **not reschedule cards or change normal FSRS intervals**.
- Runs locally; the current version contains no network requests and does not upload the user's collection data.

## How the recommendation works

The default thematic intervals are:

`2 → 4 → 7 → 14 → 21 → 30 → 45 → 60 days`

The interval is adjusted using the most recent meaningful session. More **Again/Hard** answers can shorten the recommendation interval; very strong performance can increase it slightly.

This is a **heuristic study-planning tool**, not a scientifically validated forgetting-curve model and not a replacement for FSRS.

## Installation

1. Download the latest `.ankiaddon` file from the `releases/` folder or from the GitHub Releases page.
2. Open **Anki Desktop**.
3. Go to **Tools → Add-ons**.
4. Choose **Install from file** and select the `.ankiaddon` file.
5. Restart Anki.

> Add-ons of this type are intended for **Anki Desktop**. They are not installed directly in AnkiMobile or AnkiDroid.

## Configuration

Open the friendly settings window from:

**Tools → Study Radar Settings...**

You can also click **⚙ Settings** directly inside the Radar. No manual JSON editing is required.

Default values remain:

```text
Intervals: 2 → 4 → 7 → 14 → 21 → 30 → 45 → 60 days
History: 730 days
Max decks shown: 8
Minimum session: 5 reviews
Upcoming window: 5 days
Quick Review size: 25 cards
```

| Option | Meaning |
| --- | --- |
| `base_intervals_days` | Base sequence of thematic review intervals, in days. |
| `history_days` | How far back Study Radar looks in the local review history. |
| `max_rows` | Maximum number of decks shown in the radar. |
| `minimum_session_reviews` | Minimum number of answers needed for a day to count as a meaningful session. |
| `show_upcoming_days` | How many upcoming days are shown in addition to due/overdue decks. |
| `smart_review_cards` | Maximum number of cards selected for each Quick Review session. |

## Privacy

Study Radar reads information from the local Anki collection to calculate recommendations. **v0.3.0 does not contain network code or send review history to an external server.**

## Status

This project is currently in **beta**. Feedback, bug reports, Anki version information, and screenshots are welcome.

Planned ideas include:

- Optional deck ignore list.
- Snooze/postpone recommendations.
- Review profiles such as Standard, Intensive and Exam mode.
- Optional statistics/history view.
- Improved session detection.

## Building the `.ankiaddon`

With Python installed:

```bash
python scripts/build_addon.py
```

The generated package will be placed in `dist/`.

## License / reuse

The source is published for transparency and personal testing. **It is not released under an open-source license.** Redistribution, republishing, selling, or presenting modified copies as another project is not permitted without the copyright holder's permission. See [`LICENSE`](LICENSE).

## Author

Created by **DrCapivara-dev**.

---

## 🇧🇷 Resumo em português

O **Anki Study Radar** analisa seu histórico local e mostra na tela inicial do Anki quais **baralhos/temas valem a pena revisar hoje**. Ele usa os nomes reais dos seus baralhos, considera desempenho recente e intervalos temáticos progressivos. A **Revisão Rápida** escolhe automaticamente cards difíceis e usa modo de pré-visualização, preservando o agendamento normal/FSRS.
