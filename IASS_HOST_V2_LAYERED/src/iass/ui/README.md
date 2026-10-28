# UI structure

The live UI is a single-page app, not the multi-page set of templates the
folder used to contain. Only two routes ever get rendered:

| Route(s) | Template | JS | CSS |
|---|---|---|---|
| `/`, `/logs`, `/telemetry`, `/personnel`, `/register`, `/security`, `/hardware`, `/hardware-config`, `/settings` | `app.html` | `app_shell.js` | `app_shell.css` |
| `/camera` | `camera.html` | `phone_camera.js` | `theme.css` |

`app_shell.js` is a client-side router: every "page" (dashboard, security,
personnel, hardware, hardware-config, logs, settings, register) is a
`<div data-view-panel>` inside `app.html`, shown/hidden and populated by
`fetch()` calls as you navigate — there's no server-side page for each of
those routes even though `app.py` has a route function for each one (they
all just return the same `app.html` shell).

## What was archived

`templates/{dashboard,logs,personnel,register,telemetry}.html` and their
dedicated `static/js/{logs,personnel,registration,telemetry_poll,
stream_manager}.js` and `static/css/{logs,personnel,surveillance,
telemetry}.css` were an **earlier multi-page version** of this same UI —
one real HTML page per feature, each with its own hand-rolled polling
script. It was fully superseded by the `app.html` SPA shell but never
deleted, so the `ui/` folder had two complete, parallel UI implementations
sitting side by side. I confirmed via `grep` that `app.py` never calls
`render()` on any of those five templates, and that no live template
references their JS/CSS -- they're genuinely unreachable, not just unused
in the current run. Full copies are in
`_archive/unused_legacy_and_superseded/ui_superseded_multipage_version/`.

Also archived: two more copies of `app.js`/`app.css`/`register.js` sitting
directly under `static/` (not in `static/js/`), which were yet another,
even older dashboard implementation, referenced by nothing at all.

## If you want to go further

Right now `app_shell.js` is a single 38-line, extremely dense file handling
every view. It works and I didn't touch it, but if you want the "classified
by profession" structure to go deeper than "orphaned files removed," the
natural next step is splitting it into one small module per view
(`views/dashboard.js`, `views/security.js`, `views/personnel.js`, etc.)
that `app_shell.js` imports and dispatches to, mirroring the backend's
`/api/security/overview`, `/api/personnel/overview`, `/api/hardware/overview`
endpoints one-to-one. I left this alone in this pass since it's working,
tested-by-use code and splitting it is a larger, separate piece of work --
happy to do it as a follow-up if you want it.
