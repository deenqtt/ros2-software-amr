# Typography decision

**Date:** 2026-09-25
**Status:** accepted

## Decision

**Inter carries the entire interface, numbers included.** Numeric readouts use Inter with
`font-variant-numeric: tabular-nums` and Inter's `ss02` disambiguation set, not a monospace.

**JetBrains Mono is kept for identifiers only** — ROS topic names, TF frame ids, bridge URLs,
log lines. Two utilities express the split:

| Utility | Family | Features | Use |
|---|---|---|---|
| `.font-data` | Inter | `tnum`, `ss02`, `zero`, `calt` | Every number: pose, velocity, battery, timestamps, counts |
| `.font-ident` | JetBrains Mono | `zero`, `calt` off | Topic names, frame ids, URLs, log lines, IDs |

Body text sets `calt` and `cv08` globally. `cv08` puts a serif on the capital I.

## Why not "mono on every number"

DESIGN.md specifies CoinbaseMono on every numerical value. That rule exists because Coinbase
*has* a house monospace and wants the brand texture. It is a branding rule wearing a legibility
costume, and it does not survive contact with the substitute font.

Current guidance is the opposite for data readouts: a proportional face with tabular figures
reads better than a full monospace, and it is one CSS property rather than a second webfont —
["If you're using a monospace font purely to stop digits from jittering, you almost certainly
want `font-variant-numeric: tabular-nums` instead"](https://dev.to/alanwest/tabular-numbers-in-css-font-variant-numeric-vs-monospace-hacks-25cn).
Dashboard-specific guidance says the same and names Inter directly, for its screen origins, high
x-height and slashed-zero option ([Best Fonts for Dashboards](https://madegooddesigns.com/best-fonts-for-dashboards/)).

Tabular figures are what actually solve the problem this project has: a value updating at 30 Hz
must not shift its neighbours. `tabular-nums` fixes every digit to the same advance and
[prevents numbers jumping as values update live](https://www.myfonts.com/pages/fontscom-learning-fontology-level-3-numbers-proportional-vs-tabular-figures).
A monospace achieves the same alignment as a side effect while costing a font load and a
texture change.

## Why Inter

- **Built for this.** Designed for screen interfaces with a tall x-height, open apertures and
  vertical metrics tuned so dense text does not collide; legible below 11px
  ([rsms.me/inter](https://rsms.me/inter/)).
- **Tabular figures ship by default** — unusual for a text face, and correct for dashboards.
- **It has a disambiguation set.** `ss02` increases visual difference between similar-looking
  characters and includes a slashed zero; `ss04` is the same without the zero; `cv08` adds a
  serif to the capital I. This matters because it is the exact failure mode legacy HMI guidance
  warns about: Verdana has "a serif on '1' but similar 'l' and 'I' shapes", and Arial shows
  "poor differentiation between similar characters"
  ([HMI Font Selection](https://industrialmonitordirect.com/blogs/knowledgebase/hmi-font-selection-technical-considerations-for-industrial-operator-interface-readability)).
  Inter lets us fix that with a feature flag instead of a font change.
- **Precedent in instrumentation.** Its documented uses include
  [NASA instrumentation and medical equipment](https://rsms.me/inter/) — closer to this product
  than a marketing site is.
- **OFL licensed**, variable, on Google Fonts.

## Alternatives considered

### B612 / B612 Mono — the strongest challenger

The only candidate with research provenance for *this* problem. Airbus began a study with ENAC
and Université de Toulouse III in 2010 to define an "aeronautical font", specifically to improve
legibility on cockpit screens and reduce visual fatigue and cognitive load; the result was
open-sourced under the Eclipse Public License in 2017
([PolarSys B612](https://github.com/polarsys/b612),
[background](https://imjustcreative.com/b612-open-source-font-family/2019/01/25)). Designed for
degraded viewing conditions — variable lighting, off-axis viewing, high cognitive load. That
description is a robot operator console.

Rejected for the UI face on two grounds:

1. **It reads wrong on high-resolution desktop screens.** Its ink traps — indentations at letter
   junctions — draw immediate negative reactions on desktop displays, and the defence is that
   they function as *light* traps for poor viewing conditions
   ([design debate](https://biggo.com/news/202509031914_B612_Aviation_Font_Design_Debate)). That
   defence is sound for a cockpit at altitude. This console runs on an ordinary monitor.
2. **It is not a UI text family.** It has no equivalent of Inter's optical sizing,
   disambiguation sets or character variants, so every legibility adjustment becomes a font
   swap rather than a feature flag.

**B612 Mono is a live option for `.font-ident`.** It is the better-received of the two variants
and would signal the domain. Swapping it is a one-line change to `fontFamily.mono`. Not taken
now only because JetBrains Mono is already loaded and identifiers are a small fraction of the
text on screen.

### IBM Plex Sans + IBM Plex Mono

Sans and Mono designed together, so the pairing is coherent by construction, and Plex is built
for UI environments ([IBM/plex](https://github.com/IBM/plex)). Rejected because Inter's
small-size optical work and its disambiguation features are specifically what this interface
needs, and Plex offers no documented equivalent.

### Verdana + Courier New

What legacy HMI vendor guidance actually recommends: Verdana 10pt for labels and buttons,
Courier New 10pt for I/O status, alarm lists and numeric data, chosen partly because custom
fonts get substituted on panels that do not have them
([SCADA HMI design guidance](https://industrialmonitordirect.com/blogs/knowledgebase/hmi-font-selection-technical-considerations-for-industrial-operator-interface-readability)).

Rejected as advice for a different platform — a WinCC panel with no webfont pipeline, where
"available on every system" outranks everything. A browser loading a self-describing webfont has
no such constraint. **Two principles from it are kept**, because they are real and predate the
font choice:

- Character differentiation is safety-relevant, not cosmetic → hence `ss02` and `cv08`.
- Numeric and tabular data deserve different typographic treatment from prose → hence the
  `.font-data` / `.font-ident` split, and tabular figures everywhere a number appears.

## Consequences

- One webfont does almost all the work; the monospace is a small secondary load.
- Character disambiguation is a feature flag, so it can be tuned per context without a font swap.
- Departs from DESIGN.md's "CoinbaseMono on every number" rule. The rule's intent — numbers are
  never set like prose — is honoured by `.font-data`.
- Every new numeric readout must carry `.font-data`. A number set in plain body text will jitter
  as it updates, and that is a review item, not a preference.

## Sources

- [Inter font family](https://rsms.me/inter/)
- [Tabular Numbers in CSS: font-variant-numeric vs Monospace Hacks](https://dev.to/alanwest/tabular-numbers-in-css-font-variant-numeric-vs-monospace-hacks-25cn)
- [Best Fonts for Dashboards (Data-Legible UI)](https://madegooddesigns.com/best-fonts-for-dashboards/)
- [Proportional vs. Tabular Figures](https://www.myfonts.com/pages/fontscom-learning-fontology-level-3-numbers-proportional-vs-tabular-figures)
- [HMI Font Selection: Technical Considerations for Industrial Operator Interface Readability](https://industrialmonitordirect.com/blogs/knowledgebase/hmi-font-selection-technical-considerations-for-industrial-operator-interface-readability)
- [PolarSys B612 font family](https://github.com/polarsys/b612)
- [B612 Open Source Font Family — Designed for Aircraft Cockpit Screens](https://imjustcreative.com/b612-open-source-font-family/2019/01/25)
- [B612 Aviation Font Sparks Debate Over Design Choices for Cockpit Displays](https://biggo.com/news/202509031914_B612_Aviation_Font_Design_Debate)
- [IBM Plex](https://github.com/IBM/plex)
