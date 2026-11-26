# HealthVerse A+B visual system

Captured 2026-11-26 for the HealthVerse web workspace. This file records the visual decisions used in the implementation; it does not authorize reuse of third-party artwork.

## References inspected

1. Personalized Rehabilitation Dashboard (方案 A) — https://dribbble.com/shots/24921473-Web-App-UI-UX-Personalized-Rehabilitation-Dashboard
   - Screenshot context: desktop rehabilitation workspace with a stable left navigation rail, calm white canvas, progress-oriented cards and a strong central task area.
   - Reused as a structural reference only: navigation density, whitespace, card hierarchy, and calm clinical rhythm.
2. Health Monitoring / MedFlow (方案 B) — https://dribbble.com/shots/26780137-Health-Monitoring-Medical-Dashboard-App-UI-Design
   - Screenshot context: card-based health monitoring dashboard with soft emotional color blocks and low-contrast surfaces.
   - Reused as a softness reference only: low-contrast surfaces and restrained health-dashboard accents. The final implementation deliberately removes its pink, green, and yellow families.
The slight hand-drawn line variation is a user-specified constraint, not a third visual reference. All colors below are implementation estimates derived from A and B, not extracted brand assets.

The later user-supplied scientific-method diagram is used only as line-language guidance: white-paper whitespace, sparse pencil-like outlines, varied dashed arrows, and lightly hatched annotations. Its yellow/green palette is intentionally not carried into the interface.

## Design tokens

| Role | Token | Value | Meaning |
|---|---|---:|---|
| Canvas | `--canvas` | `#F7F9FF` | quiet pale-blue workspace |
| Main surface | `--paper` | `#FFFFFF` | A-style white task surface |
| Perception | `--mist-blue` | `#EEF4FF` | near-white powder-blue input tint |
| Verification | `--soft-mint` | `#EEF4FF` | legacy token name; same powder-blue paper tint |
| Constraint | `--warning-yellow` | `#EEF4FF` | legacy token name; same powder-blue paper tint |
| Ink | `--ink` | `#8395B4` | light slate-blue text and line work |
| Micro accent | `--orange` | `#AAB9D5` | pale periwinkle focus marker only |

## Typography

- Display and labels: Patrick Hand + LXGW WenKai for the bilingual hand-annotated academic character.
- Body: the same stack is retained for stylistic consistency, but body contrast and line height are kept product-like.
- Hierarchy: large Chinese task heading, small uppercase method cue, compact evidence labels.

## Layout and components

- 246 px left rail, large content canvas, 34 px desktop page padding.
- The live workspace keeps one dominant video region and one narrower Agent region.
- Card backgrounds are mostly neutral. Semantic color appears only at region headers or states.
- Borders remain deliberately non-uniform through radius, dash and tiny rotation differences, but use 1–1.5 px ink instead of heavy 3–5 px contours.
- Shadows are soft ambient shadows rather than comic offset blocks.
- Input, options, verified states, and constraints all use the same near-white blue-gray paper tint. Meaning is carried by border style, line weight, labels, and small shadows—not by green or yellow fills. Pink is not used.

## Motion

- Keep the existing 240–520 ms view-transition choreography.
- Hover movement is limited to 1–2 px and never blocks camera/video interaction.
- Respect `prefers-reduced-motion`.

## Image policy

- No Dribbble screenshot or third-party illustration is bundled in the product.
- The live video surface is user-provided camera/video content; decorative scenes remain local vector/CSS artwork.
