# Hormonia Frontend Design System

This document provides comprehensive documentation for the Hormonia clinic frontend design system, covering all design tokens, component variants, and usage guidelines.

---

## Table of Contents

1. [Color Palette](#color-palette)
2. [Typography](#typography)
3. [Spacing](#spacing)
4. [Border Radius](#border-radius)
5. [Shadows](#shadows)
6. [Z-Index Scale](#z-index-scale)
7. [Component Variants](#component-variants)
8. [Breakpoints](#breakpoints)
9. [Animation](#animation)
10. [Dark Mode](#dark-mode)

---

## Color Palette

The design system uses **OKLCH** color space for perceptually uniform colors. All colors are defined as CSS custom properties in `/src/app/styles/index.css`.

### Core Colors

| Token | Light Mode (OKLCH) | Description |
|-------|-------------------|-------------|
| `--background` | `oklch(1 0 0)` | Page background (pure white) |
| `--foreground` | `oklch(0.145 0 0)` | Primary text color (near black) |
| `--primary` | `oklch(0.205 0 0)` | Primary brand color |
| `--primary-foreground` | `oklch(0.985 0 0)` | Text on primary backgrounds |
| `--secondary` | `oklch(0.97 0 0)` | Secondary/subtle backgrounds |
| `--secondary-foreground` | `oklch(0.205 0 0)` | Text on secondary backgrounds |

### Surface Colors

| Token | Light Mode (OKLCH) | Description |
|-------|-------------------|-------------|
| `--card` | `oklch(1 0 0)` | Card surface color |
| `--card-foreground` | `oklch(0.145 0 0)` | Card text color |
| `--popover` | `oklch(1 0 0)` | Popover/dropdown surface |
| `--popover-foreground` | `oklch(0.145 0 0)` | Popover text color |
| `--muted` | `oklch(0.97 0 0)` | Muted/subtle backgrounds |
| `--muted-foreground` | `oklch(0.556 0 0)` | Subdued text (labels, hints) |
| `--accent` | `oklch(0.97 0 0)` | Accent backgrounds (hover states) |
| `--accent-foreground` | `oklch(0.205 0 0)` | Accent text |

### Semantic Colors

| Token | Light Mode (OKLCH) | Description |
|-------|-------------------|-------------|
| `--destructive` | `oklch(0.577 0.245 27.325)` | Error/danger states (red) |
| `--success` | `oklch(0.723 0.191 142.5)` | Success states (green) |
| `--success-foreground` | `oklch(0.985 0 0)` | Text on success backgrounds |
| `--warning` | `oklch(0.795 0.184 86.047)` | Warning states (amber) |
| `--warning-foreground` | `oklch(0.21 0.006 285.885)` | Text on warning backgrounds |
| `--info` | `oklch(0.623 0.214 259.815)` | Informational states (blue) |
| `--info-foreground` | `oklch(0.985 0 0)` | Text on info backgrounds |

### Form & Interactive Colors

| Token | Light Mode (OKLCH) | Description |
|-------|-------------------|-------------|
| `--border` | `oklch(0.922 0 0)` | Default border color |
| `--input` | `oklch(0.922 0 0)` | Input field borders |
| `--ring` | `oklch(0.708 0 0)` | Focus ring color |

### Chart Colors

| Token | OKLCH Value | Use Case |
|-------|------------|----------|
| `--chart-1` | `oklch(0.646 0.222 41.116)` | Primary chart series |
| `--chart-2` | `oklch(0.6 0.118 184.704)` | Secondary chart series |
| `--chart-3` | `oklch(0.398 0.07 227.392)` | Tertiary chart series |
| `--chart-4` | `oklch(0.828 0.189 84.429)` | Fourth chart series |
| `--chart-5` | `oklch(0.769 0.188 70.08)` | Fifth chart series |

### Sidebar Colors

| Token | Light Mode (OKLCH) | Description |
|-------|-------------------|-------------|
| `--sidebar` | `oklch(0.985 0 0)` | Sidebar background |
| `--sidebar-foreground` | `oklch(0.145 0 0)` | Sidebar text |
| `--sidebar-primary` | `oklch(0.205 0 0)` | Sidebar primary accent |
| `--sidebar-primary-foreground` | `oklch(0.985 0 0)` | Text on sidebar primary |
| `--sidebar-accent` | `oklch(0.97 0 0)` | Sidebar hover states |
| `--sidebar-accent-foreground` | `oklch(0.205 0 0)` | Text on sidebar accent |
| `--sidebar-border` | `oklch(0.922 0 0)` | Sidebar borders |
| `--sidebar-ring` | `oklch(0.708 0 0)` | Sidebar focus rings |

### Usage Examples

```tsx
// Using semantic colors in components
<div className="bg-primary text-primary-foreground">
  Primary button
</div>

<div className="bg-destructive text-white">
  Error message
</div>

<div className="bg-success text-success-foreground">
  Success notification
</div>

<div className="bg-warning text-warning-foreground">
  Warning alert
</div>

<div className="bg-info text-info-foreground">
  Info tooltip
</div>
```

---

## Typography

The design system uses two primary font families for clear visual hierarchy.

### Font Families

| Token | Font Stack | Usage |
|-------|------------|-------|
| `font-heading` | `'Poppins', system-ui, -apple-system, sans-serif` | Headings (h1-h6), titles |
| `font-body` | `'Roboto', system-ui, -apple-system, sans-serif` | Body text, paragraphs |
| `font-sans` | `'Roboto', system-ui, -apple-system, sans-serif` | Default sans-serif |
| `font-mono` | `'Roboto Mono', ui-monospace, SFMono-Regular, monospace` | Code, numeric displays |

### Font Sizes

| Token | Size | Line Height | Font Weight | Usage |
|-------|------|-------------|-------------|-------|
| `text-heading-1` | `2rem` (32px) | `1.2` | `600` | Page titles |
| `text-heading-2` | `1.5rem` (24px) | `1.2` | `600` | Section headings |
| `text-heading-3` | `1.25rem` (20px) | `1.2` | `500` | Subsection headings |
| `text-body` | `1rem` (16px) | `1.5` | `400` | Body text |
| `text-body-sm` | `0.875rem` (14px) | `1.5` | `400` | Small body text |
| `text-label` | `0.875rem` (14px) | `1.5` | `500` | Form labels |
| `text-numeric` | `1rem` (16px) | `1.5` | `400` | Tabular numbers (with `tnum`) |

### Heading Styles (Base Layer)

```css
h1 {
  font-family: 'Poppins', system-ui, -apple-system, sans-serif;
  font-size: 2rem;
  line-height: 1.2;
  font-weight: 600;
}

h2 {
  font-family: 'Poppins', system-ui, -apple-system, sans-serif;
  font-size: 1.5rem;
  line-height: 1.2;
  font-weight: 600;
}

h3 {
  font-family: 'Poppins', system-ui, -apple-system, sans-serif;
  font-size: 1.25rem;
  line-height: 1.2;
  font-weight: 500;
}
```

### Usage Examples

```tsx
// Heading with custom font
<h1 className="font-heading text-heading-1">Dashboard</h1>

// Body text
<p className="font-body text-body">Patient information...</p>

// Small text with label styling
<label className="text-label text-muted-foreground">Email Address</label>

// Numeric display with tabular numbers
<span className="text-numeric font-mono">R$ 1,234.56</span>
```

---

## Spacing

The design system uses Tailwind's default spacing scale based on `0.25rem` (4px) increments.

### Spacing Scale

| Class | Value | Pixels | Common Usage |
|-------|-------|--------|--------------|
| `0` | `0` | 0px | No spacing |
| `0.5` | `0.125rem` | 2px | Tight gaps |
| `1` | `0.25rem` | 4px | Minimal spacing |
| `1.5` | `0.375rem` | 6px | Small gaps |
| `2` | `0.5rem` | 8px | Compact spacing |
| `3` | `0.75rem` | 12px | Moderate spacing |
| `4` | `1rem` | 16px | Standard spacing |
| `5` | `1.25rem` | 20px | Medium spacing |
| `6` | `1.5rem` | 24px | Card padding |
| `8` | `2rem` | 32px | Section spacing |
| `10` | `2.5rem` | 40px | Large spacing |
| `12` | `3rem` | 48px | Extra-large spacing |
| `16` | `4rem` | 64px | Huge spacing |

### Container Configuration

```javascript
container: {
  center: true,
  padding: "2rem",  // 32px
  screens: {
    "2xl": "1400px",  // Max container width
  },
}
```

### Usage Examples

```tsx
// Card with standard padding
<Card className="p-6">  {/* 24px padding */}
  <CardHeader className="px-6 gap-1.5">
    <CardTitle>Title</CardTitle>
  </CardHeader>
</Card>

// Form field spacing
<div className="space-y-4">  {/* 16px gap between children */}
  <Input />
  <Input />
</div>

// Section margin
<section className="mt-8 mb-12">  {/* 32px top, 48px bottom */}
```

---

## Border Radius

The design system uses a base radius variable with calculated variants.

### Radius Tokens

| Token | Value | Calculation | Pixels (at default) |
|-------|-------|-------------|---------------------|
| `--radius` | `0.625rem` | Base value | 10px |
| `--radius-sm` | `calc(var(--radius) - 4px)` | Smaller variant | 6px |
| `--radius-md` | `calc(var(--radius) - 2px)` | Medium variant | 8px |
| `--radius-lg` | `var(--radius)` | Large (default) | 10px |
| `--radius-xl` | `calc(var(--radius) + 4px)` | Extra large | 14px |

### Tailwind Mappings

| Class | CSS Value |
|-------|-----------|
| `rounded-sm` | `calc(var(--radius) - 4px)` |
| `rounded-md` | `calc(var(--radius) - 2px)` |
| `rounded-lg` | `var(--radius)` |

### Usage Examples

```tsx
// Button with default radius
<Button className="rounded-md">Submit</Button>

// Card with large radius
<Card className="rounded-xl">Content</Card>

// Input with medium radius
<Input className="rounded-md" />

// Pill-shaped badge
<Badge className="rounded-full">New</Badge>
```

---

## Shadows

The design system uses Tailwind's shadow utilities for elevation.

### Shadow Scale

| Class | Description | Use Case |
|-------|-------------|----------|
| `shadow-xs` | Extra small shadow | Buttons, inputs |
| `shadow-sm` | Small shadow | Cards, dropdowns |
| `shadow` | Default shadow | Modals, floating elements |
| `shadow-md` | Medium shadow | Dialogs |
| `shadow-lg` | Large shadow | Overlays |
| `shadow-xl` | Extra large shadow | Popovers |
| `shadow-2xl` | Double extra large | Major overlays |

### Component Shadow Usage

| Component | Shadow Class |
|-----------|-------------|
| Button (default) | `shadow-xs` |
| Button (destructive) | `shadow-xs` |
| Card | `shadow-sm` |
| Dropdown | `shadow-md` |
| Dialog/Modal | `shadow-lg` |
| Popover | `shadow-xl` |

### Usage Examples

```tsx
// Card with subtle shadow
<Card className="shadow-sm">Content</Card>

// Elevated button
<Button className="shadow-xs hover:shadow-sm">Click</Button>

// Modal overlay
<Dialog className="shadow-lg">
  <DialogContent>...</DialogContent>
</Dialog>
```

---

## Z-Index Scale

### Current Usage (Needs Standardization)

The codebase does not have a formalized z-index scale. Below is a **recommended standardization**:

### Recommended Z-Index Scale

| Token | Value | Use Case |
|-------|-------|----------|
| `z-0` | `0` | Base level |
| `z-10` | `10` | Sticky headers, elevated cards |
| `z-20` | `20` | Fixed sidebars |
| `z-30` | `30` | Dropdown menus |
| `z-40` | `40` | Drawer overlays |
| `z-50` | `50` | Modal/Dialog overlays |
| `z-60` | `60` | Tooltips |
| `z-70` | `70` | Notifications/Toasts |
| `z-80` | `80` | Loading overlays |
| `z-90` | `90` | Global error modals |
| `z-[100]` | `100` | Maximum priority |

### Implementation Recommendation

Add to `tailwind.config.js`:

```javascript
theme: {
  extend: {
    zIndex: {
      'sticky': '10',
      'sidebar': '20',
      'dropdown': '30',
      'drawer': '40',
      'modal': '50',
      'tooltip': '60',
      'toast': '70',
      'overlay': '80',
      'critical': '90',
    },
  },
}
```

### Usage Examples

```tsx
// Sticky header
<header className="sticky top-0 z-sticky">...</header>

// Sidebar navigation
<nav className="fixed z-sidebar">...</nav>

// Modal dialog
<Dialog className="z-modal">...</Dialog>

// Toast notifications
<Toaster className="z-toast" />
```

---

## Component Variants

### Button Component

Located at: `/src/components/ui/button.tsx`

#### Variants

| Variant | Styles | Use Case |
|---------|--------|----------|
| `default` | `bg-primary text-primary-foreground shadow-xs hover:bg-primary/90` | Primary actions |
| `destructive` | `bg-destructive text-white shadow-xs hover:bg-destructive/90` | Delete, danger actions |
| `outline` | `border bg-background shadow-xs hover:bg-accent` | Secondary actions |
| `secondary` | `bg-secondary text-secondary-foreground shadow-xs hover:bg-secondary/80` | Tertiary actions |
| `ghost` | `hover:bg-accent hover:text-accent-foreground` | Subtle/icon buttons |
| `link` | `text-primary underline-offset-4 hover:underline` | Text links |

#### Sizes

| Size | Styles | Use Case |
|------|--------|----------|
| `default` | `h-11 px-4 py-2` | Standard buttons |
| `sm` | `h-10 rounded-md gap-1.5 px-3` | Compact buttons |
| `lg` | `h-12 rounded-md px-6` | Large/hero buttons |
| `icon` | `size-11` | Icon-only buttons |

#### Usage Examples

```tsx
import { Button } from "@/components/ui/button"

// Primary action
<Button variant="default">Save Changes</Button>

// Danger action
<Button variant="destructive">Delete Patient</Button>

// Secondary action
<Button variant="outline">Cancel</Button>

// Icon button
<Button variant="ghost" size="icon">
  <SearchIcon />
</Button>

// Large CTA
<Button variant="default" size="lg">Get Started</Button>
```

---

### Badge Component

Located at: `/src/components/ui/badge.tsx`

#### Variants

| Variant | Styles | Use Case |
|---------|--------|----------|
| `default` | `bg-primary text-primary-foreground` | Default state |
| `secondary` | `bg-secondary text-secondary-foreground` | Subtle indicators |
| `destructive` | `bg-destructive text-white` | Errors, warnings |
| `outline` | `text-foreground` border only | Neutral tags |

#### Usage Examples

```tsx
import { Badge } from "@/components/ui/badge"

// Status indicators
<Badge variant="default">Active</Badge>
<Badge variant="secondary">Pending</Badge>
<Badge variant="destructive">Overdue</Badge>
<Badge variant="outline">Draft</Badge>

// As link
<Badge asChild>
  <a href="/patients">View All</a>
</Badge>
```

---

### Alert Component

Located at: `/src/components/ui/alert.tsx`

#### Variants

| Variant | Styles | Use Case |
|---------|--------|----------|
| `default` | `bg-card text-card-foreground` | Informational alerts |
| `destructive` | `text-destructive bg-card` | Error messages |

#### Sub-components

- `Alert` - Container with role="alert"
- `AlertTitle` - Bold heading
- `AlertDescription` - Descriptive text

#### Usage Examples

```tsx
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert"
import { AlertCircle, CheckCircle } from "lucide-react"

// Error alert
<Alert variant="destructive">
  <AlertCircle className="h-4 w-4" />
  <AlertTitle>Error</AlertTitle>
  <AlertDescription>
    Failed to save patient record. Please try again.
  </AlertDescription>
</Alert>

// Info alert
<Alert>
  <CheckCircle className="h-4 w-4" />
  <AlertTitle>Success</AlertTitle>
  <AlertDescription>
    Patient record updated successfully.
  </AlertDescription>
</Alert>
```

---

### Card Component

Located at: `/src/components/ui/card.tsx`

#### Sub-components

| Component | Usage |
|-----------|-------|
| `Card` | Main container with `rounded-xl border shadow-sm` |
| `CardHeader` | Header area with auto-grid layout |
| `CardTitle` | Main title with `font-heading font-semibold` |
| `CardDescription` | Subtitle with `text-muted-foreground` |
| `CardAction` | Top-right action slot |
| `CardContent` | Main content area |
| `CardFooter` | Bottom actions area |

#### Usage Examples

```tsx
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  CardFooter,
  CardAction
} from "@/components/ui/card"

<Card>
  <CardHeader>
    <CardTitle>Patient Information</CardTitle>
    <CardDescription>View and edit patient details</CardDescription>
    <CardAction>
      <Button variant="ghost" size="icon">
        <MoreHorizontal />
      </Button>
    </CardAction>
  </CardHeader>
  <CardContent>
    <p>Patient data here...</p>
  </CardContent>
  <CardFooter>
    <Button>Save</Button>
  </CardFooter>
</Card>
```

---

### Input Component

Located at: `/src/components/ui/input.tsx`

#### Styles

| State | Classes |
|-------|---------|
| Default | `border-input bg-transparent rounded-md h-11` |
| Focus | `focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]` |
| Invalid | `aria-invalid:ring-destructive/20 aria-invalid:border-destructive` |
| Disabled | `disabled:pointer-events-none disabled:opacity-50` |
| Dark Mode | `dark:bg-input/30` |

#### Usage Examples

```tsx
import { Input } from "@/components/ui/input"

// Basic input
<Input type="text" placeholder="Enter patient name" />

// With validation error
<Input
  type="email"
  aria-invalid={errors.email ? true : false}
  placeholder="Email address"
/>

// Disabled state
<Input type="text" disabled value="Read only" />
```

---

## Breakpoints

The design system uses Tailwind's default responsive breakpoints.

### Breakpoint Scale

| Breakpoint | Min Width | CSS |
|------------|-----------|-----|
| `sm` | `640px` | `@media (min-width: 640px)` |
| `md` | `768px` | `@media (min-width: 768px)` |
| `lg` | `1024px` | `@media (min-width: 1024px)` |
| `xl` | `1280px` | `@media (min-width: 1280px)` |
| `2xl` | `1400px` | `@media (min-width: 1400px)` |

**Note:** The `2xl` breakpoint is customized to `1400px` (default Tailwind uses `1536px`).

### Container Behavior

```css
/* Container padding */
@media (width >= 640px) {
  .container {
    padding-inline: 2rem;
  }
}

/* Default mobile */
.container {
  margin-inline: auto;
  padding-inline: 1rem;
}
```

### Usage Examples

```tsx
// Responsive grid
<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
  {/* Grid items */}
</div>

// Responsive text
<h1 className="text-xl sm:text-2xl lg:text-3xl xl:text-4xl">
  Dashboard
</h1>

// Responsive spacing
<section className="p-4 sm:p-6 lg:p-8 xl:p-10">
  Content
</section>

// Hide on mobile
<nav className="hidden md:flex">Desktop nav</nav>
<nav className="flex md:hidden">Mobile nav</nav>
```

---

## Animation

### Keyframes

Defined in `tailwind.config.js`:

| Animation | Description | Duration |
|-----------|-------------|----------|
| `accordion-down` | Expand accordion content | `0.2s ease-out` |
| `accordion-up` | Collapse accordion content | `0.2s ease-out` |
| `shimmer` | Skeleton loading effect | `2s ease-in-out infinite` |
| `breathing` | Pulsing opacity effect | `3s ease-in-out infinite` |
| `wave` | Horizontal wave motion | `2s ease-in-out infinite` |
| `skeleton-wave` | Skeleton wave effect | `2s ease-in-out infinite` |
| `spin` | Rotation animation | `0.8s linear infinite` |

### Keyframe Definitions

```javascript
keyframes: {
  "accordion-down": {
    from: { height: 0 },
    to: { height: "var(--radix-accordion-content-height)" },
  },
  "accordion-up": {
    from: { height: "var(--radix-accordion-content-height)" },
    to: { height: 0 },
  },
  shimmer: {
    "0%": { "background-position": "-200% 0" },
    "100%": { "background-position": "200% 0" },
  },
  breathing: {
    "0%": { opacity: "0.4" },
    "50%": { opacity: "1" },
    "100%": { opacity: "0.4" },
  },
  wave: {
    "0%": { transform: "translateX(-100%)" },
    "50%": { transform: "translateX(100%)" },
    "100%": { transform: "translateX(100%)" },
  },
}
```

### Animation Classes

| Class | Animation |
|-------|-----------|
| `animate-accordion-down` | `accordion-down 0.2s ease-out` |
| `animate-accordion-up` | `accordion-up 0.2s ease-out` |
| `animate-shimmer` | `shimmer 2s ease-in-out infinite` |
| `animate-breathing` | `breathing 3s ease-in-out infinite` |
| `animate-wave` | `wave 2s ease-in-out infinite` |
| `animate-skeleton-wave` | `skeleton-wave 2s ease-in-out infinite` |
| `animate-spin` | `spin 0.8s linear infinite` |

### Reduced Motion Support

The CSS respects `prefers-reduced-motion`:

```css
@media (prefers-reduced-motion: reduce) {
  .animate-wave,
  .animate-shimmer,
  .animate-breathing,
  .animate-pulse,
  .animate-spin {
    animation: none;
  }
}
```

### Usage Examples

```tsx
// Loading spinner
<div className="animate-spin h-5 w-5 border-2 border-primary rounded-full border-t-transparent" />

// Skeleton loader
<div className="animate-shimmer bg-muted h-4 rounded" />

// Breathing effect for loading states
<div className="animate-breathing bg-primary/20 p-4 rounded">
  Loading...
</div>

// Accordion (via Radix)
<AccordionContent className="data-[state=open]:animate-accordion-down data-[state=closed]:animate-accordion-up">
  Content
</AccordionContent>
```

---

## Dark Mode

Dark mode is implemented using the `class` strategy with Tailwind CSS.

### Configuration

```javascript
// tailwind.config.js
module.exports = {
  darkMode: ["class"],
  // ...
}
```

```css
/* index.css */
@custom-variant dark (&:is(.dark *));
```

### Dark Mode Color Tokens

| Token | Light | Dark |
|-------|-------|------|
| `--background` | `oklch(1 0 0)` | `oklch(0.145 0 0)` |
| `--foreground` | `oklch(0.145 0 0)` | `oklch(0.985 0 0)` |
| `--card` | `oklch(1 0 0)` | `oklch(0.205 0 0)` |
| `--primary` | `oklch(0.205 0 0)` | `oklch(0.922 0 0)` |
| `--primary-foreground` | `oklch(0.985 0 0)` | `oklch(0.205 0 0)` |
| `--secondary` | `oklch(0.97 0 0)` | `oklch(0.269 0 0)` |
| `--muted` | `oklch(0.97 0 0)` | `oklch(0.269 0 0)` |
| `--muted-foreground` | `oklch(0.556 0 0)` | `oklch(0.708 0 0)` |
| `--accent` | `oklch(0.97 0 0)` | `oklch(0.371 0 0)` |
| `--destructive` | `oklch(0.577 0.245 27.325)` | `oklch(0.704 0.191 22.216)` |
| `--border` | `oklch(0.922 0 0)` | `oklch(1 0 0 / 10%)` |
| `--input` | `oklch(0.922 0 0)` | `oklch(1 0 0 / 15%)` |
| `--ring` | `oklch(0.708 0 0)` | `oklch(0.556 0 0)` |

### Dark Mode Chart Colors

| Token | Light | Dark |
|-------|-------|------|
| `--chart-1` | `oklch(0.646 0.222 41.116)` | `oklch(0.488 0.243 264.376)` |
| `--chart-2` | `oklch(0.6 0.118 184.704)` | `oklch(0.696 0.17 162.48)` |
| `--chart-3` | `oklch(0.398 0.07 227.392)` | `oklch(0.769 0.188 70.08)` |
| `--chart-4` | `oklch(0.828 0.189 84.429)` | `oklch(0.627 0.265 303.9)` |
| `--chart-5` | `oklch(0.769 0.188 70.08)` | `oklch(0.645 0.246 16.439)` |

### Usage Examples

```tsx
// Toggle dark mode class on html element
document.documentElement.classList.toggle('dark')

// Conditional dark mode styles
<div className="bg-white dark:bg-gray-900">
  <p className="text-gray-900 dark:text-gray-100">Content</p>
</div>

// Component-specific dark variants
<Button className="dark:bg-input/30 dark:border-input dark:hover:bg-input/50">
  Dark-aware button
</Button>

// Input with dark mode background
<Input className="dark:bg-input/30" />
```

### Theme Toggle Implementation

```tsx
import { useTheme } from 'next-themes'
import { Moon, Sun } from 'lucide-react'

function ThemeToggle() {
  const { theme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
    >
      <Sun className="h-5 w-5 dark:hidden" />
      <Moon className="h-5 w-5 hidden dark:block" />
    </Button>
  )
}
```

---

## Utilities

### cn() Helper Function

Located at: `/src/lib/utils.ts`

Combines `clsx` and `tailwind-merge` for optimal class merging:

```typescript
import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
```

### Usage

```tsx
import { cn } from "@/lib/utils"

// Merge conditional classes
<div className={cn(
  "base-class",
  isActive && "active-class",
  variant === "primary" && "bg-primary"
)}>

// Override classes safely
<Button className={cn(buttonVariants({ variant, size }), className)}>
```

### Scrollbar Hide Utility

```css
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
```

---

## File Structure

```
frontend-hormonia/
├── tailwind.config.js          # Tailwind configuration
├── src/
│   ├── app/
│   │   └── styles/
│   │       └── index.css       # Global styles & CSS variables
│   ├── components/
│   │   └── ui/
│   │       ├── button.tsx      # Button component
│   │       ├── badge.tsx       # Badge component
│   │       ├── alert.tsx       # Alert component
│   │       ├── card.tsx        # Card component
│   │       ├── input.tsx       # Input component
│   │       └── ...             # Other UI components
│   └── lib/
│       └── utils.ts            # Utility functions (cn, formatDate, etc.)
└── docs/
    └── design-system/
        └── DESIGN_SYSTEM.md    # This file
```

---

## Quick Reference

### Color Utilities

```tsx
// Backgrounds
bg-background bg-foreground bg-primary bg-secondary bg-destructive
bg-muted bg-accent bg-card bg-popover bg-success bg-warning bg-info

// Text
text-foreground text-primary text-secondary text-destructive
text-muted-foreground text-accent-foreground text-success-foreground

// Borders
border-border border-input border-ring border-destructive
```

### Typography Utilities

```tsx
// Font families
font-heading font-body font-mono font-sans

// Font sizes
text-heading-1 text-heading-2 text-heading-3
text-body text-body-sm text-label text-numeric
```

### Layout Utilities

```tsx
// Spacing
p-4 p-6 px-6 py-3 gap-2 gap-4 space-y-4

// Border radius
rounded-sm rounded-md rounded-lg rounded-xl rounded-full

// Shadows
shadow-xs shadow-sm shadow shadow-md shadow-lg
```

### Interactive States

```tsx
// Hover
hover:bg-primary/90 hover:bg-accent hover:underline

// Focus
focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:border-ring

// Disabled
disabled:pointer-events-none disabled:opacity-50

// Invalid
aria-invalid:border-destructive aria-invalid:ring-destructive/20
```

---

## Contributing

When adding new design tokens or components:

1. Define CSS custom properties in `/src/app/styles/index.css`
2. Add Tailwind mappings in `tailwind.config.js` if needed
3. Update this documentation
4. Include both light and dark mode values
5. Follow the established naming conventions
6. Test across all breakpoints

---

*Last updated: December 2024*
