# Professional Dashboard UI/UX Redesign Plan

## Overview
Transform the current dark-mode-only dashboard into a professional, dual-theme (light/dark) application with flat design, consistent visual language, and polished UI/UX across all components.

**Scope:** Visual/design changes only. Zero functional changes to data flow, APIs, or business logic.

---

## Current Issues Identified

### 1. Theme System
- **Dark mode only** - all colors hardcoded in `:root` with no light mode variants
- No theme toggle or persistence mechanism
- Background uses radial gradient effects that feel casual

### 2. Button Design
- `btn-primary` uses gradient: `linear-gradient(135deg, var(--accent), var(--accent2))`
- Hover uses `brightness(1.1)` filter + translateY transform
- Inconsistent secondary button hover states

### 3. Sidebar
- Uses glass-panel effect with backdrop blur
- Close button inside sidebar (✕ character)
- No icons on nav items - text only
- No visual grouping/sectioning of nav items
- Active state uses subtle glow background

### 4. Header
- Glass-panel with backdrop blur
- Uses emoji-like characters for toggle (✕, ☰)
- No avatar, just plain text for user name
- Role shown as a node badge

### 5. Tables
- Inline styles throughout
- No zebra striping or row hover effects
- Minimal header styling
- No responsive behavior for mobile

### 6. Cards & Panels
- Heavy use of glass-panel everywhere
- Inconsistent border-radius (12px, 16px, var(--radius))
- Hover effect is translateY + border color change

### 7. Modals
- Basic overlay with glass-panel content
- No animation on open/close
- Form fields use inline styles mixed with classes

### 8. Typography
- Single font family (Segoe UI)
- No consistent type scale
- Logo uses gradient text effect
- Inconsistent heading sizes

### 9. Forms
- Inputs have glow focus state (box-shadow)
- No validation styling
- Select elements use default browser styling

### 10. No Footer
- No footer component exists

### 11. Icons
- Uses emoji characters (👥, 🎓, 🏫, 📚, 📁)
- No SVG icon system

---

## Design Preferences (User-Confirmed)

- **Style**: Clean & Minimal (Apple/Linear-inspired: lots of whitespace, subtle borders, minimal shadows, focus on content)
- **Sidebar**: Full-height fixed sidebar (extends from top to bottom of viewport, content scrolls beside it)
- **Default Theme**: Light mode (with dark mode toggle available)
- **Icons**: Custom inline SVGs (no dependencies, lightweight, fully customizable)

## Design System Definition

### Color Palette

#### Light Theme (Default)
```css
--bg-primary: #fafafa;        /* Main background */
--bg-secondary: #ffffff;      /* Cards, panels */
--bg-tertiary: #f4f4f5;       /* Inputs, nested surfaces */
--bg-hover: #f0f0f2;          /* Hover states */

--border-subtle: #e4e4e7;     /* Light borders */
--border-default: #d4d4d8;    /* Default borders */

--text-primary: #18181b;      /* Primary text */
--text-secondary: #52525b;    /* Secondary text */
--text-muted: #a1a1aa;        /* Muted/placeholder */

--accent-primary: #2563eb;    /* Primary action */
--accent-hover: #1d4ed8;      /* Hover state */
--accent-muted: rgba(37, 99, 235, 0.06); /* Subtle accent bg */

--success: #16a34a;
--success-bg: rgba(22, 163, 74, 0.06);
--success-text: #15803d;
--warning: #d97706;
--warning-bg: rgba(217, 119, 6, 0.06);
--warning-text: #b45309;
--error: #dc2626;
--error-bg: rgba(220, 38, 38, 0.06);
--error-text: #b91c1c;
--info: #2563eb;
--info-bg: rgba(37, 99, 235, 0.06);
--info-text: #1d4ed8;
```

#### Dark Theme
```css
--bg-primary: #09090b;        /* Main background */
--bg-secondary: #18181a;      /* Cards, panels */
--bg-tertiary: #27272a;       /* Inputs, nested surfaces */
--bg-hover: #3f3f46;          /* Hover states */

--border-subtle: #27272a;     /* Light borders */
--border-default: #3f3f46;    /* Default borders */

--text-primary: #fafafa;      /* Primary text */
--text-secondary: #a1a1aa;    /* Secondary text */
--text-muted: #71717a;        /* Muted/placeholder */

--accent-primary: #3b82f6;    /* Primary action */
--accent-hover: #60a5fa;      /* Hover state */
--accent-muted: rgba(59, 130, 246, 0.1); /* Subtle accent bg */

--success: #22c55e;
--success-bg: rgba(34, 197, 94, 0.1);
--success-text: #4ade80;
--warning: #f59e0b;
--warning-bg: rgba(245, 158, 11, 0.1);
--warning-text: #fbbf24;
--error: #ef4444;
--error-bg: rgba(239, 68, 68, 0.1);
--error-text: #f87171;
--info: #3b82f6;
--info-bg: rgba(59, 130, 246, 0.1);
--info-text: #60a5fa;
```

### Typography Scale
```
xs:   0.75rem  (12px)  - Badges, captions
sm:   0.875rem (14px)  - Secondary text, labels
base: 1rem     (16px)  - Body text
md:   1.125rem (18px)  - Subheadings
lg:   1.25rem  (20px)  - Section headings
xl:   1.5rem   (24px)  - Page headings
2xl:  1.875rem (30px)  - Hero headings
3xl:  2.25rem  (36px)  - Welcome screens
```

### Spacing Scale
```
xs:  0.25rem (4px)
sm:  0.5rem  (8px)
md:  1rem    (16px)
lg:  1.5rem  (24px)
xl:  2rem    (32px)
2xl: 3rem    (48px)
3xl: 4rem    (64px)
```

### Border Radius
```
sm:   6px   - Small elements (badges, small inputs)
md:   8px   - Buttons, inputs
lg:   12px  - Cards, panels
xl:   16px  - Modals, large containers
full: 9999px - Pills, round elements
```

### Shadows
```
sm:  0 1px 2px rgba(0, 0, 0, 0.05)
md:  0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)
lg:  0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)
xl:  0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)
```

---

## Implementation Steps

### Step 1: Theme Infrastructure (`globals.css` + Layout Context)

**Files to modify:**
- `frontend/src/app/globals.css`
- `frontend/src/components/LayoutContext.tsx` (extend with theme state)

**Changes:**
1. Restructure `globals.css`:
   - Define light mode colors as default in `:root`
   - Add `[data-theme="dark"]` selector with dark palette
   - Remove body radial gradient background (replace with solid `--bg-primary`)
   - Replace gradient buttons with flat colors
   - Add new typography scale classes
   - Add new shadow utility classes
   - Remove glass-panel backdrop-filter blur (replace with solid backgrounds + subtle borders)
   - Add transition for theme switching on all themed properties

2. Extend `LayoutContext.tsx` with theme state:
   - Add `theme` state ('light' | 'dark')
   - `toggleTheme()` function
   - Read system preference via `prefers-color-scheme` (fallback to 'light')
   - Persist choice in `localStorage`
   - Apply `data-theme` attribute to `<html>` element via useEffect
   - Export `useTheme()` hook alongside `useLayout()`

3. Update `layout.tsx`:
   - Wrap with LayoutProvider (now includes theme)
   - Add `suppressHydrationWarning` on `<html>` (already present)

**Button redesign (flat, no gradient):**
```css
.btn-primary {
  background: var(--accent-primary);
  color: white;
  box-shadow: none;
}

.btn-primary:hover {
  background: var(--accent-hover);
  box-shadow: none;
  transform: none;
  filter: none;
}

.btn-primary:active {
  background: var(--accent-primary);
  transform: scale(0.98);
}
```

---

### Step 2: Sidebar Redesign (Full-Height Fixed)

**File to modify:**
- `frontend/src/components/Sidebar.tsx`

**Changes:**
1. Change sidebar positioning:
   - Full viewport height (`height: 100vh`, `top: 0`)
   - Fixed position on left side
   - Solid background (`--bg-secondary`)
   - Right border instead of rounded edges
   - Content area shifts right to accommodate sidebar

2. Replace glass-panel with solid surface:
   - No backdrop blur
   - Subtle right border (`1px solid --border-subtle`)
   - Clean, minimal aesthetic

3. Add section grouping with labels:
   - "OVERVIEW" section: Dashboard
   - "MANAGE" section: Users, Students, Classes, Subjects
   - "ASSESSMENTS" section: Exams, Result Schemas
   - "ACCOUNT" section: Change Password
   - Section labels: uppercase, small (11px), muted color, letter-spacing

4. Add SVG icons to each nav item (20x20, aligned left):
   - Dashboard: grid icon
   - Users: users/group icon
   - Students: graduation cap
   - Classes: building icon
   - Subjects: book icon
   - Exams: clipboard icon
   - Result Schemas: database/schema icon
   - Change Password: lock icon

5. Improve active state:
   - Left border accent (2px) in accent color
   - Subtle accent-muted background
   - Accent-colored text
   - Remove glow effect

6. Hover state:
   - Subtle `--bg-hover` background
   - No border change, no transform

7. Nav item layout:
   - Icon + label in flex row
   - Gap between icon and text (12px)
   - Padding: 8px 16px
   - Border-radius: 6px

8. Transition: smooth theme transitions on all elements

---

### Step 3: Header Redesign (Minimal)

**File to modify:**
- `frontend/src/components/Header.tsx`

**Changes:**
1. Change from glass-panel to minimal header:
   - Solid background (`--bg-secondary`)
   - Bottom border (`1px solid --border-subtle`)
   - No backdrop blur
   - Reduced height (64px)
   - Position: sticky top, or integrated with sidebar layout

2. Left section:
   - Remove toggle button (sidebar always visible on desktop, overlay on mobile)
   - Simple logo: "AI PDF Processing" in bold, no gradient text
   - Use custom SVG icon next to logo

3. Right section:
   - Theme toggle button: sun/moon SVG icon, circular button
     - Size: 36x36px
     - Border: 1px solid --border-subtle
     - Background: transparent, hover uses --bg-hover
     - No text, icon only
   - User area: circular avatar (32px) with initials + accent background
   - User name next to avatar in secondary text color
   - Logout: small icon button with logout icon, tooltip on hover

4. Remove role badge from header (redundant)

5. Clean spacing and alignment:
   - Flex layout, space-between
   - Proper padding (0 24px)
   - Height: 64px

---

### Step 4: Main Content Area

**File to modify:**
- `frontend/src/components/MainContent.tsx`

**Changes:**
1. Remove glass-panel dependency
2. Update container layout:
   - Add left margin equal to sidebar width on desktop
   - Remove left margin on mobile/tablet
3. Proper background (`--bg-primary`)
4. Consistent padding
5. Remove animate-fade-in from main wrapper
6. Footer added at bottom of main content area

---

### Step 5: Table Styling System

**Changes (CSS in globals.css):**
1. Create consistent table classes:
```css
.table-container {
  overflow-x: auto;
  border-radius: var(--radius-lg);
  border: 1px solid var(--border-subtle);
}

.table {
  width: 100%;
  border-collapse: collapse;
}

.table thead {
  background: var(--bg-tertiary);
  border-bottom: 2px solid var(--border-default);
}

.table th {
  padding: var(--padding-md) var(--padding-lg);
  text-align: left;
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.table td {
  padding: var(--padding-md) var(--padding-lg);
  border-bottom: 1px solid var(--border-subtle);
  font-size: var(--text-sm);
}

.table tbody tr {
  background: var(--bg-secondary);
  transition: background var(--transition-fast);
}

.table tbody tr:hover {
  background: var(--bg-hover);
}

.table tbody tr:last-child td {
  border-bottom: none;
}
```

2. Update all table usages across pages to use these classes:
   - `frontend/src/app/exams/page.tsx`
   - `frontend/src/app/students/page.tsx`
   - `frontend/src/app/users/page.tsx`
   - `frontend/src/app/classes/page.tsx`
   - `frontend/src/app/subjects/page.tsx`
   - `frontend/src/app/result-schemas/page.tsx`

---

### Step 6: Card & Panel Redesign

**Changes (CSS in globals.css):**
1. Update card styles:
```css
.card {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  padding: var(--padding-xl);
  transition: box-shadow var(--transition-fast);
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: none;  /* Remove translateY */
  border-color: var(--border-default);
}
```

2. Replace glass-panel with `.panel`:
```css
.panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
}
```

3. Update all usages of `glass-panel` class to use `.panel`

---

### Step 7: Modal Redesign

**Changes (CSS in globals.css):**
1. Update modal overlay:
```css
.modal-overlay {
  background: rgba(0, 0, 0, 0.5);  /* Darker, more opaque */
  backdrop-filter: blur(4px);       /* Subtle blur on overlay only */
}

.modal-content {
  background: var(--bg-secondary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-xl);
  padding: var(--padding-xl);
}
```

2. Add entrance animation:
```css
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.95) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-content {
  animation: modalIn 0.2s ease-out;
}
```

---

### Step 8: Form Elements Redesign

**Changes (CSS in globals.css):**
1. Update input styles:
```css
.form-input, .input-field {
  background: var(--bg-tertiary);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: var(--padding-sm) var(--padding-md);
  color: var(--text-primary);
  font-size: var(--text-sm);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.form-input:focus, .input-field:focus {
  outline: none;
  border-color: var(--accent-primary);
  box-shadow: 0 0 0 3px var(--accent-muted);  /* Subtle, no glow */
}
```

2. Update select elements to have custom styling
3. Add validation states (success/error borders)
4. Improve label typography

---

### Step 9: Status Badges Redesign

**Changes (CSS in globals.css):**
1. Keep node badges but refine colors for both themes
2. Update status-badge styles to use theme variables
3. Ensure proper contrast in both light and dark modes
4. Add consistent padding, border-radius, and font-weight

---

### Step 10: Footer Component

**New file:**
- `frontend/src/components/Footer.tsx`

**Changes:**
1. Create a simple, clean footer:
   - Solid background (bg-secondary or bg-tertiary)
   - Top border
   - Left: Copyright, product name
   - Right: Version info, links (if needed)
2. Add to `MainContent.tsx` or `layout.tsx`
3. Responsive: stack on mobile

```css
.app-footer {
  background: var(--bg-secondary);
  border-top: 1px solid var(--border-subtle);
  padding: var(--padding-md) var(--padding-xl);
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-xs);
  color: var(--text-muted);
}
```

---

### Step 11: Icon System

**New directory:**
- `frontend/src/components/icons/`

**Changes:**
1. Create simple SVG icon components (20x20, currentColor, no fill):
   - `IconDashboard.tsx` - 4-square grid
   - `IconUsers.tsx` - two person silhouettes
   - `IconStudents.tsx` - graduation cap
   - `IconClasses.tsx` - building
   - `IconSubjects.tsx` - open book
   - `IconExams.tsx` - clipboard with checkmark
   - `IconSchemas.tsx` - database/cylinder
   - `IconPassword.tsx` - key
   - `IconMenu.tsx` - hamburger lines
   - `IconClose.tsx` - X mark
   - `IconSun.tsx` - sun with rays
   - `IconMoon.tsx` - crescent moon
   - `IconLogout.tsx` - arrow from door
   - `IconSearch.tsx` - magnifying glass
   - `IconChevronDown.tsx` - chevron
   - `IconPlus.tsx` - plus sign
   - `IconEdit.tsx` - pencil
   - `IconTrash.tsx` - trash can
   - `IconDownload.tsx` - download arrow
   - `IconUpload.tsx` - upload arrow
   - `IconFile.tsx` - document
   - `IconCheck.tsx` - checkmark

2. All icons: consistent 20x20 viewBox, stroke-width 1.5, no fill
3. Replace all emoji usage throughout the app with these SVG icons

---

### Step 12: Page-Level Updates

Update each page to use the new design system classes and remove inline styles:

1. **Dashboard (`page.tsx`)**:
   - Remove inline styles, use design system classes
   - Update card grid layout
   - Replace emoji with icons
   - Improve welcome section layout

2. **Exams (`exams/page.tsx`)**:
   - Replace inline table styles with `.table` classes
   - Update filter bar to use panel class
   - Improve modal layout
   - Remove inline styles

3. **Students (`students/page.tsx`)**:
   - Replace inline table styles
   - Update filter bar layout
   - Improve modal styling
   - Remove inline styles

4. **Users (`users/page.tsx`)**:
   - Same as Students page
   - Consistent table and modal styling

5. **Classes, Subjects, Result Schemas**:
   - Apply consistent table/card styling
   - Remove inline styles

6. **Login (`login/page.tsx`)**:
   - Improve card styling
   - Better spacing and typography
   - Remove inline styles

7. **Exam detail pages (`exams/[id]/page.tsx`, etc.)**:
   - Apply consistent styling
   - Update any unique components

---

### Step 13: Responsive Improvements

**Changes:**
1. Ensure all components work well at:
   - Desktop (>1200px)
   - Tablet (768px - 1199px)
   - Mobile (<768px)
2. Sidebar:
   - Full overlay on mobile
   - Partial width on tablet
3. Tables:
   - Horizontal scroll on mobile
   - Consider card layout for mobile
4. Modals:
   - Full-screen on mobile
   - Proper padding

---

## Implementation Order

For maximum efficiency, implement steps in this order:

1. Theme Infrastructure - Foundation for everything else
2. Icon System - Needed by sidebar and header
3. Sidebar Redesign - Core navigation structure
4. Header Redesign - Top bar with theme toggle
5. Main Content + Footer - Layout wrapper
6. CSS Redesign - Tables, cards, forms, badges, buttons (globals.css)
7. Dashboard Page - Landing page redesign
8. Data Pages - Exams, Students, Users, Classes, Subjects, Result Schemas
9. Auth Pages - Login, Forgot Password, Change Password
10. Responsive Polish - Mobile/tablet adjustments

## Phased Implementation Plan

For reduced risk, easier debugging, and manageable sessions, implementation is split into **3 phases**:

---

### Phase 1: Foundation (Infrastructure + Layout + Design System)

**Goal:** Establish the visual foundation — theme system, icons, layout components, and CSS design tokens.

| # | Step | Files Changed | Deliverable |
|---|------|---------------|-------------|
| 1 | Theme Infrastructure | `globals.css`, `LayoutContext.tsx`, `layout.tsx` | Light/dark theme with toggle, persistence, system preference |
| 2 | Icon System | `frontend/src/components/icons/*.tsx` (22 files) | All SVG icons ready for use |
| 3 | Sidebar Redesign | `Sidebar.tsx` | Full-height fixed sidebar with icons, sections, new states |
| 4 | Header Redesign | `Header.tsx` | Solid header with avatar, theme toggle, SVG icons |
| 5 | Main Content + Footer | `MainContent.tsx`, `Footer.tsx` (new) | Clean wrapper with footer |
| 6 | CSS Design System | `globals.css` | Tables, cards, forms, badges, buttons, typography, shadows |

**Files touched:** ~28 files (22 new icon files + 6 modified)
**Exit criteria:** Dev server runs, both themes work, sidebar/header/footer render correctly on dashboard (page content may look unstyled still)

---

### Phase 2: Page Application (Data Pages + Dashboard)

**Goal:** Apply the design system to all pages — remove inline styles, use new CSS classes, replace emoji with icons.

| # | Step | Files Changed | Deliverable |
|---|------|---------------|-------------|
| 7 | Dashboard Page | `page.tsx` | Welcome section, card grid, icons, no inline styles |
| 8 | Exams Pages | `exams/page.tsx`, `exams/[id]/page.tsx`, `exams/[id]/batches/page.tsx`, `exams/[id]/upload/page.tsx` + subcomponents | Tables, modals, filter bars using design system |
| 9 | Students Pages | `students/page.tsx`, `students/me/page.tsx` | Tables, modals, filter bars using design system |
| 10 | Users Page | `users/page.tsx` | Tables, modals, filter bars using design system |
| 11 | Classes, Subjects, Schemas | `classes/page.tsx`, `subjects/page.tsx`, `result-schemas/page.tsx` | Consistent table/card/modal styling |
| 12 | Sheet Detail | `sheets/[id]/page.tsx` | Consistent styling |

**Files touched:** ~15 files
**Exit criteria:** All pages render with new design system in both light and dark modes. Zero inline styles remaining.

---

### Phase 3: Polish (Auth Pages + Responsive + QA)

**Goal:** Finish auth pages, responsive breakpoints, cross-theme QA, and cleanup.

| # | Step | Files Changed | Deliverable |
|---|------|---------------|-------------|
| 13 | Auth Pages | `login/page.tsx`, `forgot-password/page.tsx`, `reset-password/page.tsx`, `change-password/page.tsx` | Consistent card/input styling, typography |
| 14 | Responsive Polish | `globals.css`, `Sidebar.tsx`, `Header.tsx`, `MainContent.tsx` | Mobile overlay sidebar, table scroll, modal full-screen |
| 15 | QA & Cleanup | All files | Cross-theme testing, remove `.glass-panel` alias if ready, final polish |

**Files touched:** ~8 files
**Exit criteria:** All success criteria met (see below). App works at all breakpoints in both themes.

---

### Execution Order

```
Phase 1 (Foundation)
    ↓
Phase 2 (Page Application)
    ↓
Phase 3 (Polish & QA)
```

Each phase is self-contained and can be completed in a single focused session. Do not proceed to the next phase until the current phase's exit criteria are met.

---

## File Change Summary

| File | Action | Description |
|------|--------|-------------|
| `globals.css` | Modify | Theme variables (light default + dark), flat buttons, typography, tables, cards, forms, shadows |
| `LayoutContext.tsx` | Modify | Add theme state, toggle, localStorage persistence, system preference detection |
| `Header.tsx` | Modify | Solid bg, user avatar, theme toggle button, SVG icons, remove glass effect |
| `Sidebar.tsx` | Modify | Full-height fixed, section grouping, SVG icons, solid bg, improved states |
| `MainContent.tsx` | Modify | Clean wrapper, sidebar offset, footer inclusion |
| `Footer.tsx` | Create | Simple footer component |
| `layout.tsx` | Modify | No changes needed (already has suppressHydrationWarning) |
| `icons/*.tsx` | Create | ~22 SVG icon components (no dependencies) |
| `page.tsx` | Modify | Dashboard page redesign, remove inline styles |
| `login/page.tsx` | Modify | Login page styling improvements |
| `exams/page.tsx` | Modify | Table classes, panel classes, remove inline styles |
| `students/page.tsx` | Modify | Table classes, panel classes, remove inline styles |
| `users/page.tsx` | Modify | Table classes, panel classes, remove inline styles |
| `classes/page.tsx` | Modify | Consistent styling |
| `subjects/page.tsx` | Modify | Consistent styling |
| `result-schemas/page.tsx` | Modify | Consistent styling |
| `exams/[id]/page.tsx` | Modify | Consistent styling |
| `exams/[id]/upload/` | Modify | Consistent styling for upload/mapping pages |
| `sheets/[id]/page.tsx` | Modify | Consistent styling |
| `students/me/page.tsx` | Modify | Consistent styling |

---

## Risks & Considerations

1. **Hydration mismatch**: Theme applied via `data-theme` on `<html>` may cause Next.js hydration warnings. Solution: Use `suppressHydrationWarning` on `<html>` and apply theme in `useEffect`.

2. **CSS specificity**: Inline styles throughout the codebase may override CSS classes. Solution: Remove inline styles systematically during implementation.

3. **Breaking changes**: The glass-panel class is used extensively. Solution: Keep `.glass-panel` as an alias for `.panel` during transition.

4. **Theme persistence**: Must read localStorage on client-side only to avoid SSR issues.

5. **Testing**: Each page should be tested in both light and dark modes after changes.

---

## Success Criteria

- [ ] Theme toggle works and persists across sessions
- [ ] System preference (light/dark) respected on first visit
- [ ] All buttons use flat colors (no gradients)
- [ ] Sidebar has section grouping and SVG icons
- [ ] Header has user avatar and theme toggle
- [ ] Tables use consistent styling system
- [ ] Cards and panels have solid backgrounds (no glass/blur)
- [ ] Forms have consistent input styling
- [ ] Footer is present on all pages
- [ ] All emoji replaced with SVG icons
- [ ] Zero functional changes (all APIs, data flow unchanged)
- [ ] Responsive at all breakpoints
- [ ] Smooth theme transition (no flash)
