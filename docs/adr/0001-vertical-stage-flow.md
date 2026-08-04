# Roadmap stages flow vertically with left-to-right node rows

DEV-66 asked for a roadmap.sh-style layout, but roadmap.sh alternates nodes left and right of a central spine (a zigzag), which is not what the ticket actually described — it asked for stages top-to-bottom with branch nodes reading left-to-right. We followed the ticket: stages stack vertically on a gold spine, and each stage's nodes flow left-to-right in a wrapping `auto-fit` grid. **This deviation from roadmap.sh is deliberate — do not "fix" it into a zigzag.**

Two reasons decided it. A wrapping grid degrades to a single column on a phone, where a zigzag has nowhere to go; and left-to-right rows let a row's dotted rail be drawn as the top border of gapless grid cells, so the connectors need no row chunking, no measurement and no SVG at any node count. A zigzag would have required knowing each node's side and height in JS.

The previous layout was the same idea rotated 90°: stages as side-by-side columns inside a horizontally scrolling canvas. That was a holdover from when the roadmap was one section in the scrolling single-page app; DEV-65 gave it its own route, so it now uses the page's natural axis and never scrolls sideways.
