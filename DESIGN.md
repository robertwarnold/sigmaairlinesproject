# Sigma Airlines analytics design system

## Surface and reference

Mode: Operate. An executive-first engineering workspace with persistent navigation for
five destinations. Use compact white surfaces on a neutral gray canvas and reveal
technical diagnostics and source evidence through explicit view links and disclosures.

## Tokens

Canvas #f7f8fa; surface #ffffff; raised #eef2f5; headings #33414c; secondary text
#65737e; primary blue #387fb5; border #e0e5e9. Semantic rose #d77982 marks high
severity/failure; neutral gray marks unrated records. Do not equate color with formal
risk acceptance. Standard Segoe UI/Arial typography, 13px body, 23px page title,
19px section headings, 12px chart headings. Cards use thin borders, 5px radius,
13-15px padding, and no decorative shadows.

## Composition

Persistent primary navigation, a compact global filter disclosure, and a visible scope strip.
On mobile the same routes are reachable through a labeled native selector. Show applicable
cohort counts and move snapshot provenance into a disclosure.
The executive brief uses five compact metrics, one coverage chart, findings and a decision.
Engineering Quality, Experiments & Performance, Financial Impact and Data Explorer carry
their own evidence. Technical tables scroll within their containers. Review details, finance
assumptions and the academic poster use disclosures.

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
