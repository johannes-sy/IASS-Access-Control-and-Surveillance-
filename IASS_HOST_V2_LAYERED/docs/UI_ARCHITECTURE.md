# IASS Workstation UI Architecture

The IASS host UI is a workstation-style application shell, not a collection of independent web pages.

## Shell

- Fixed viewport application shell with a compact navigation rail.
- Main content uses internal scrolling rather than allowing the camera stream to change the page width.
- Primary camera feed is constrained to a 16:9 container and uses `object-fit: contain`.
- Views are routed by the left navigation: Operations, Security, Personnel, Hardware, Audit, Enrollment and Settings.

## Separation of concerns

The browser layer is divided into:

- `templates/app.html` — application shell and view markup.
- `static/css/app_shell.css` — visual system, layout and components.
- `static/js/app_shell.js` — navigation and view-specific data controllers.
- Existing legacy templates/assets remain available for compatibility.

The UI consumes semantic APIs. It does not implement security decisions, AI recognition, UART protocols or device pin mappings.

## Operations

The Operations view is intentionally compact. It contains the primary surveillance feed, camera selector, AI assessment, current subject and a short security pulse. Detailed investigations are moved to dedicated views.

## Security

The Security Center separates routine observations from suspicious/high-risk/security-alert events. It provides severity filters and an emergency-stop action that calls the existing hardware safety API.

## Personnel

Presence is presented as an observation read model derived from the existing event stream. The UI does not invent entry/exit records when the underlying system has no such sensor event. Full audit records remain available through the Audit view.

## Hardware

The Hardware Control Center consumes the existing `HardwareStateManager` and hardware command history. It exposes current state, status, fault and recent command information without exposing low-level serial details to the operator UI.

## Settings

Runtime AI and tracking controls use the existing `/api/ai` and `/api/tracking` APIs. Static configuration values are displayed from the active IASS settings so operators can see which camera, serial, AI and hardware configuration is actually active.
