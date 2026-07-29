# AGENTS.md — /frontend
 
Read `/AGENTS.md` (root) first for project-wide rules. This file covers frontend-specific conventions.
 
## Stack
 
- React 18 + TypeScript, built with Vite
- Tailwind CSS for styling (utility-first; avoid inline styles and CSS-in-JS)
- TanStack Query for server state / data fetching
- Zustand (or React Context for simple cases) for local UI state
- `@monaco-editor/react` or CodeMirror 6 for the LaTeX editor pane
- API calls go through a single typed client in `/src/lib/api.ts` — do not call `fetch` directly from components
## Design Direction (must be followed on every screen)
 
- Minimalist but elegant: generous whitespace, one neutral base color + one accent color used sparingly, strong typographic hierarchy over decoration.
- No generic "AI SaaS" visual tropes — no purple-blue gradients, no glowing blobs, no default-Bootstrap rounded-everything look.
- Typography-led: a distinctive heading font + a highly legible body/UI font, defined once as CSS variables/Tailwind theme tokens, used consistently.
- Motion is functional only (state transitions, compile status, approval state) — never decorative.
- Every screen must support both light and dark mode via CSS variables/Tailwind's dark mode, not per-component overrides.
- Fully responsive down to mobile: the split-pane LaTeX editor + PDF preview must stack vertically on narrow viewports, not just shrink horizontally.
- Accessible by default: sufficient contrast, keyboard-navigable forms and editor controls, semantic HTML elements (not div-soup).
## Folder Structure
 
```
/frontend
  /src
    /components      # shared, reusable UI components
    /screens          # one folder per top-level screen (dashboard, skill-bank, jd-input, match-review, editor, integrations)
    /lib
      api.ts          # typed API client
      types.ts        # types mirroring backend Pydantic schemas
    /hooks             # shared React hooks (e.g. usePollJobStatus)
    /store              # Zustand stores, if used
    /styles             # Tailwind config, theme tokens, global CSS
  index.html
  vite.config.ts
```
 
## Conventions
 
1. **Type everything against the backend contract.** Every API response type in `/src/lib/types.ts` should mirror the corresponding FastAPI Pydantic schema. If the backend schema changes, update types here in the same PR.
2. **No silent auto-apply UI.** Any screen displaying AI-generated content (rewritten bullets, matched skills, inferred GitHub/LeetCode skills) must render an explicit approve/reject or accept/dismiss control — never a state that looks already-committed until the user acts.
3. **Distinguish inferred vs. self-reported data visually**, not just in a tooltip — e.g., a persistent badge/label, not a hover-only hint.
4. **Every screen needs loading, empty, and error states.** Do not ship a screen with only the happy path implemented.
5. **Async operations show real progress.** JD parsing, matching, rewriting, sync, and compilation are backend background jobs — poll or subscribe to status and reflect actual state (queued/running/failed/done) in the UI, not a generic spinner.
6. **Component size discipline.** If a screen component exceeds ~200 lines, extract subcomponents into `/components`.
## Before Submitting Changes
 
- `npm run lint`
- `tsc --noEmit`
- `npm run build` (must succeed with no errors)
- Manually verify the changed screen in both light and dark mode, and at a mobile viewport width.