# Theme development guide

**Not yet built.** Two honest options, not yet decided (see
`docs/design-log/open-source-project-structure.md` §4 - this is an open
decision, not an oversight):

- **Minimal:** the Mini App inherits Telegram's light/dark theme via the
  WebApp SDK's theme params (background/text/button colors) - "theming"
  is just consistently using those CSS variables. Close to zero extra
  architecture.
- **Full:** a proper theme system - swappable color tokens/layouts beyond
  what Telegram provides, possibly user-selectable. A real feature with
  its own design work.

This page gets filled in once that decision is made and the Mini App
project (`miniapp/`) has enough structure to hang a theme system on.
