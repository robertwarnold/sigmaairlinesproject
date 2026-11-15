# Sigma Airlines analytics design system

## Surface and reference

Mode: Operate. One continuously scrollable engineering analytics report. The supplied
Engineering Team Dashboard screenshot is the approved reference: compact Metabase-style
white cards on a neutral gray canvas. This replaces the former dark six-view shell.

## Tokens

Canvas #f7f8fa; surface #ffffff; raised #eef2f5; headings #33414c; secondary text
#65737e; primary blue #387fb5; border #e0e5e9. Semantic rose #d77982 marks high
severity/failure; neutral gray marks unrated records. Do not equate color with formal
risk acceptance. Standard Segoe UI/Arial typography, 13px body, 23px page title,
19px section headings, 12px chart headings. Cards use thin borders, 5px radius,
13-15px padding, and no decorative shadows.

## Composition

Compact title and actions, global filters, dataset provenance, six desktop KPIs,
attention summary, two-column risk charts, paired/triple AI charts, full-width FMEA
register. Use a responsive 12-column chart grid with 10px gaps. KPIs become three
columns at laptop widths and two on small screens. Technical tables scroll within
their own container. Details/reviews remain inline; no primary sidebar or tab routes.
Financial assumptions and study-level academic context use ordinary disclosures.

## Charts and evidence

Python calculates selected counts/rates; SVG/HTML place marks only. Use common scales,
subtle grids, readable units and native hover titles. Unknown is not zero. Citation
presence is not verified support. Structural validation is not engineering approval.
Historical report aggregates never masquerade as individual observations. Synthetic
fixtures carry explicit labels and never populate production snapshots automatically.
Academic ggplot exports retain separate constructors and study-level context.

## Interaction

Global filters, search, attention, matrix selection, register and exports share the
same selected row IDs. Show active record filters with a clear action. Clicks/keyboard
activation open inline record context without navigation. Preserve append-only human
review and original values. Focus outlines, reduced motion, graceful empty/error states,
manual refresh and 30-second polling remain required. Private row access remains
opt-in and loopback-only; public dashboards consume sanitized aggregates only.
