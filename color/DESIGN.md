---
name: Atmospheric Serenity
colors:
  surface: '#f9f9ff'
  surface-dim: '#cfdaf2'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f3ff'
  surface-container: '#e7eeff'
  surface-container-high: '#dee8ff'
  surface-container-highest: '#d8e3fb'
  on-surface: '#111c2d'
  on-surface-variant: '#444656'
  inverse-surface: '#263143'
  inverse-on-surface: '#ecf1ff'
  outline: '#747688'
  outline-variant: '#c4c5d9'
  surface-tint: '#1f49ef'
  primary: '#002cb5'
  on-primary: '#ffffff'
  primary-container: '#1040e8'
  on-primary-container: '#c3cbff'
  inverse-primary: '#bac3ff'
  secondary: '#486179'
  on-secondary: '#ffffff'
  secondary-container: '#c9e2ff'
  on-secondary-container: '#4c657d'
  tertiary: '#3f4140'
  on-tertiary: '#ffffff'
  tertiary-container: '#565857'
  on-tertiary-container: '#cececd'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dee1ff'
  primary-fixed-dim: '#bac3ff'
  on-primary-fixed: '#001159'
  on-primary-fixed-variant: '#0031c5'
  secondary-fixed: '#cee5ff'
  secondary-fixed-dim: '#b0c9e5'
  on-secondary-fixed: '#001d33'
  on-secondary-fixed-variant: '#304960'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c7c6'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#f9f9ff'
  on-background: '#111c2d'
  surface-variant: '#d8e3fb'
typography:
  display-hero:
    fontFamily: Space Grotesk
    fontSize: 56px
    fontWeight: '700'
    lineHeight: 60px
    letterSpacing: -0.04em
  display-hero-mobile:
    fontFamily: Space Grotesk
    fontSize: 38px
    fontWeight: '700'
    lineHeight: 42px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 44px
    letterSpacing: -0.03em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 34px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: -0.01em
  editorial-memo:
    fontFamily: Newsreader
    fontSize: 20px
    fontWeight: '400'
    lineHeight: 30px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
  body-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.04em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1.25rem
  gutter-desktop: 2rem
  margin: 1rem
  margin-desktop: 2.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2.5rem
---

## Brand & Style

This design system establishes a reflective, intimate emotional social environment designed for asynchronous empathy, authentic sentiment sharing, and quiet digital connection. It marries the serene, contemplative atmosphere of cool steel-blue mineral surfaces and cyanotype botanical prints with the raw, personal tactility of paper memos and the punchy clarity of contemporary Swiss editorial type.

The aesthetic fuses **Glassmorphism**, **Editorial Sensibility**, and **Subtle Tactility**:
- Translucent frosted glass vessels layer seamlessly over tactile, fine-grain horizontal brushed-steel and periwinkle atmospheres.
- High-contrast electric cobalt accents command focus, providing energy and functional intentionality against passive pastel undertones.
- Analog, journal-inspired elements—such as ruled memo notes, delicate line-art halftones, and paperclip motifs—ground the digital interface in emotional, diary-like safety.
- The interface evokes introspection, calm attentiveness, and intellectual honesty, avoiding the aggressive visual clutter of conventional dopamine-driven social feeds.

## Colors

The color palette hinges on atmospheric cool tones punctuated by hyper-saturated cobalt blue.

- **Primary (`#1040E8`)**: Vivid Cobalt Blue. Used deliberately for focal typography, active interactive triggers, primary chat actions, badge states, and vibrant punctuation marks.
- **Secondary (`#8EA7C2`)**: Steel Periwinkle. Used for soft ambient badges, secondary graphic silhouettes, floral halftone tints, and subtle divider strokes.
- **Tertiary (`#FBFBFA`)**: Warm Note White. Emulates tactile notebook paper and index cards, introducing domestic warmth and soft contrast against cool glass panes.
- **Neutral (`#1E293B`)**: Deep Slate Navy. Anchor text color ensuring crisp readability and high editorial contrast. Secondary neutral typography shifts to `#64748B` (Muted Slate) for timestamps, secondary labels, and metadata.
- **Atmospheric Canvas Background (`#DCE5EE` to `#C8D6E5`)**: A brushed, cool-slate sky gradient tinted with slight grain texture.
- **Glass Surfaces**: `rgba(255, 255, 255, 0.72)` with a 16px to 24px backdrop blur and a crisp, light border `rgba(255, 255, 255, 0.6)`.

## Typography

The typography strategy creates dynamic balance between geometric precision and poetic intimacy.

- **Primary Display & Titles (Space Grotesk)**: Chosen for its geometric, confident proportions and idiosyncratic rhythm. In heavy weights, it reproduces the electric poster typography visible in the core visual identity (`what is going on?`), driving assertive, modern communication.
- **Interface & Messaging Text (Plus Jakarta Sans)**: Handles reading comfort, conversational UI, threads, and high-density chat logs with humanistic clarity and soft terminal curves.
- **Expressive Mood Insets & Journal Memos (Newsreader / Editorial Serif)**: Used selectively for long-form mood shares, pinned personal affirmations, status quotes, and date stamps. Its literary elegance provides emotional vulnerability inside memo-card interfaces.

## Elevation & Depth

Visual depth is achieved through translucent atmosphere, light refraction, and low-viscosity diffused shadows rather than heavy drop-shadows.

- **Level 0 (Atmospheric Canvas)**: The textured steel-blue brushed ground with ambient cyanotype halftone illustrations embedded at 10%–20% opacity.
- **Level 1 (Submerged Glass Panes / Channels & Rails)**:
  - Surface: `rgba(255, 255, 255, 0.45)`
  - Backdrop Filter: `blur(12px)`
  - Border: 1px solid `rgba(255, 255, 255, 0.35)`
  - Shadow: None.
- **Level 2 (Floating Cards, Chat Bubbles, Modals)**:
  - Surface: `rgba(255, 255, 255, 0.78)`
  - Backdrop Filter: `blur(20px)`
  - Border: 1px solid `rgba(255, 255, 255, 0.65)`
  - Shadow: `0 8px 32px -4px rgba(16, 64, 232, 0.08), 0 2px 8px -2px rgba(30, 41, 59, 0.05)`
- **Level 3 (Tactile Paper Memos & Active Overlays)**:
  - Surface: `#FBFBFA` (Opaque warm paper note)
  - Border: 1px solid `rgba(226, 232, 240, 0.8)`
  - Shadow: `0 14px 36px -6px rgba(15, 23, 42, 0.12), 0 4px 12px -2px rgba(16, 64, 232, 0.06)`
  - Accents: Metallic paperclip anchors and subtle ruled blue lines (`rgba(16, 64, 232, 0.07)`).

## Shapes

The shape vocabulary employs soft, welcoming geometric curves to counter mechanical stiffness while maintaining architectural structure.

- **Containers & Glass Panels**: 16px (`rounded-lg`) border radius across all primary chat shells, panels, and feed cards.
- **Memos & Post-its**: Slightly tighter radii (8px to 12px) paired with micro-rotations (-1.5deg to +1.5deg) to mimic physically pinned notes.
- **Pills & Tags**: Full radius (`rounded-full`) for status indicators, emotion tags, pill buttons, and avatar frames.
- **Interactive Controls (Inputs, Buttons)**: 12px to 9999px border radius for ergonomic comfort.

## Components

### Buttons
- **Primary**: Solid Cobalt Blue (`#1040E8`) background, white text (`#FFFFFF`), full pill or 12px rounded corner. Hover state elevates through `box-shadow: 0 6px 20px rgba(16, 64, 232, 0.35)` and micro-scale up (1.02). Active scale down (0.98).
- **Glass / Secondary**: `rgba(255, 255, 255, 0.65)` frosted glass with 1px border `rgba(255, 255, 255, 0.8)`. Deep slate text (`#1E293B`).
- **Ghost / Tertiary**: Transparent base, cobalt blue hover tint (`rgba(16, 64, 232, 0.08)`), cobalt text.

### Chips & Emotion Badges
- Compact pill-shaped tags used for selecting and expressing moods (e.g., "Reflective", "Overwhelmed", "Electric", "Serene").
- Background: `rgba(255, 255, 255, 0.5)` with `1px solid rgba(142, 167, 194, 0.4)`. Text: `#1E293B`.
- Selected State: Cobalt `#1040E8` background with `#FFFFFF` text and a subtle glow.

### Conversation Bubbles
- **Incoming Messages**: Frosted glass pane (`rgba(255, 255, 255, 0.75)`), slate text (`#1E293B`), rounded-2xl with bottom-left corner tightened (4px).
- **Outgoing Messages**: Cobalt Blue (`#1040E8`), crisp white text (`#FFFFFF`), rounded-2xl with bottom-right corner tightened (4px).
- **Audio & Whispers**: Frosted steel capsule with subtle animated cobalt waveforms.

### Cards & Paper Memos
- **Feed / Ambient Card**: Glassmorphic layer with faint halftone botanical illustrations watermark in the upper right.
- **Pinned Mood Memo**: Cream card `#FBFBFA` featuring faint horizontal notebook rulings, paired with an SVG/CSS steel paperclip component pinned on the top edge. Set with serif or handwritten-leaning styling for raw human resonance.

### Input Fields & Prompt Composer
- Floating frosted bar (`rgba(255, 255, 255, 0.85)` with `backdrop-filter: blur(20px)`).
- Border: 1px solid `rgba(255, 255, 255, 0.9)`. Inner shadow creates a soft concave effect.
- Focus State: Border transitions to `#1040E8` accompanied by an outer halo `0 0 0 3px rgba(16, 64, 232, 0.15)`. Placeholder styled in muted slate `#64748B`.

### Checkboxes & Radios
- Rounded 6px boxes and circular radio rings using 1.5px `#8EA7C2` borders.
- Checked State: Filled `#1040E8` containing a sharp white icon or dot.