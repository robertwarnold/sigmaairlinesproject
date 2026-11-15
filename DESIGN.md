# Research workspace design

V4.2 premium refinement; Operate mode for the five research views and Read mode for
Presentation. This supersedes the earlier paper and V4.1 visual directions.

## Identity and tokens

Retain the existing Shiny application, native HTML/SVG charts and academic ggplots.
Mission Control opens first. Compact six-destination navigation uses a thin active
underline. Two-line brand: SIGMA AIRLINES / FMEA RESEARCH PLATFORM.

Colors live in dashboard/theme.R and become CSS variables: background #0B1016,
surface #121A23, elevated #18232E, text #EAF0F4, muted #A3B2BF, accent #62C5D1,
divider #26323E. The muted tone is deliberately brighter than the initial suggested
palette for readable small labels. Amber/failure tones indicate meaningful states.
No gradients, neon, ornamental icons, large colored metric tiles or remote fonts.

Typography uses Segoe UI/Arial for application tasks, 28px page titles, 14-15px
section headings, 12-14px operational data and 10-11px supporting labels. Consolas
is reserved for identifiers. A 4/8/12/16/24/32px spacing scale and 6px control radius
keep controls consistent. Prefer grouping with space over repeated card outlines.

## Information hierarchy

Mission: four registry/current-experiment KPIs; activity and exact-manifest progress;
recent runs. Historical aggregates and synchronization diagnostics are disclosure-only.
Registry totals span all versions; Round 2 progress matches exact manifest run IDs.
No accepted matching V4 cohort means Pending, never the historical 31.4% fallback.

Explorer: seven readable columns, ten records per page, inline filter disclosure,
selected-run detail with lifecycle history. Full IDs and metadata remain available;
mobile records reflow into a labeled list rather than a horizontally clipped table.

Quality: primary evaluated runs; secondary version comparison; expandable Pareto,
field agreement, completeness, research tables and inference details.

Finance: four clearly labeled modeled/measured outcomes and Cost comparison,
Monte Carlo, Sensitivity and Assumptions tabs. Inputs do not occupy the opening view.
Methods: seven short explanations, extended evidence and definitions on demand.
Presentation: dedicated 16:9 canvas, two ggplots, five academic content sections,
optional criteria and notes. Fullscreen hides navigation; Escape restores the workspace.
Mobile uses a reading layout rather than forcing the desktop aspect ratio.

## Interaction and integrity

Use native hover/focus, keyboard run selection and ordinary details/tab transitions.
Respect reduced motion. Preserve manual/30-second refresh and last-known-good cache.
Validated Python calculations remain authoritative. Layout, formatting, manifest-ID
selection and visual mark placement do not create or change research statistics.
Keep private records and API keys out of public/browser presentation datasets.
