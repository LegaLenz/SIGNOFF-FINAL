# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Frontend for **LegaLenz** — a contract/terms risk-analysis product. Users upload a contract (PDF or photo), the backend classifies clauses into risk grades, and this app renders the document with risk highlights plus a chat panel for explanations and suggested alternative wording.

## Commands

```bash
npm run dev      # start Vite dev server (HMR)
npm run build    # production build
npm run preview  # preview the production build locally
npm run lint     # ESLint over the project
```

No test framework is configured in this project yet.

## Architecture

### Stack

- React 19 + Vite (`@vitejs/plugin-react`)
- Tailwind CSS v4 via `@tailwindcss/vite` — **CSS-first config, no `tailwind.config.js`**. Theme tokens are declared directly in an `@theme` block inside `src/index.css` (colors like `--color-primary`, `--color-risk-high`, plus `--font-pretendard`), and Tailwind utility classes (e.g. `bg-primary`, `text-risk-high`) are generated from those custom properties.
- `react-resizable-panels` — used for the resizable two-pane analysis layout (see below).
- Pretendard font is hosted locally via the `pretendard` npm package — **not** a CDN. Install with `npm install pretendard`, then load it in `src/index.css` with `@import 'pretendard/dist/web/variable/pretendardvariable.css'`. Do not switch this to a CDN-based approach (e.g. jsdelivr).

### Design tokens: keep `src/index.css` and `src/styles/tokens.json` in sync

`src/styles/tokens.json` is the canonical design-token source (Figma Tokens Studio format: `global.color.primitive` → `global.color.semantic` references, typography, sizing, border radius). The `@theme` block in `src/index.css` is the Tailwind-consumable mirror of the same values. When a color/spacing/typography token changes, update both files — `tokens.json` is what design/Figma treats as source of truth, `index.css` is what actually drives Tailwind class generation at build time.

### Design spec

`docs/design_spec.md` is the authoritative UI/UX spec ("Quiet Intelligence" concept — Linear/Notion-like, light mode only, low-saturation neutral base). Read it before implementing UI. Key decisions already made there that affect implementation:

- **Risk grading is binary**: High vs. everything else. Only High-risk clauses get highlighted (red `#EF4444` / bg `#F7C1C1`); there is no Mid/Low tier — related tokens were deliberately removed.
- **App flow**: home screen (upload) → processing screen → analysis screen (two-pane: document panel default 65%/min 40% + chat panel default 35%/min 25%, drag-resizable).
- **No server-side history**: analysis results and chat state live only in browser session state (no persistence backend). Reset triggers, specified in the doc, are:
  - Refresh or tab close while on the analysis screen → `beforeunload` warning before leaving.
  - Clicking the back button on the analysis screen → confirmation dialog before resetting.
  - New file upload is only possible from the home screen — there is no upload entry point within the analysis screen.
- **Clause click → chat**: clicking a highlighted clause shows its cached classification in chat without re-calling the LLM; re-clicking an already-answered clause scrolls to the existing message instead of duplicating it.
- **Explicitly out of scope for MVP**: OCR text editing, PDF export of results, Mid/Low risk tiers, rich-text editing of the document panel (it's read-only).

`docs/prototype.html` is a working static HTML prototype of the full flow (home → processing → analysis) and is the reference for markup/structure and element IDs (`#dropzone`, `#doc-panel`, `#chat-panel`, `#resize-handle`, etc.) when building the real React components.

### Current implementation state

`src/App.jsx` and `src/App.css` are still the default `create-vite` scaffold — not yet replaced with the real UI. `src/components/Upload.jsx`, `src/components/Editor.jsx`, and `src/components/ChatPanel.jsx` exist as empty placeholder files mapping to the three main pieces of the flow (upload/home screen, document panel, chat panel) but have no implementation yet.
