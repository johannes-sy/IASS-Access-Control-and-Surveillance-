# UI Workstation Upgrade

## Added

- Product-grade workstation shell with persistent navigation rail.
- Dedicated Operations, Security, Personnel, Hardware, Audit, Enrollment and Settings views.
- Fixed 16:9 primary camera viewport so live streaming cannot widen the application layout.
- Camera selector with live/offline state.
- Security Center with critical/suspicious/unauthorized counts and severity filtering.
- Emergency stop action wired to the existing hardware safe-state API.
- Personnel presence read model and movement/event history.
- Hardware state center for camera mounts, doors and alarms.
- Hardware command history and fault visibility.
- Runtime AI and tracking toggles.
- Active configuration visibility.
- Centralized polling and view controllers rather than separate page-level UI implementations.

## Preserved

Existing AI, hardware, database, serial, firmware contract, registration and legacy routes/assets were not removed. The new shell consumes the existing semantic APIs.

## Validation

Run from the project root:

```bash
PYTHONPATH=src:. pytest -q
```

Expected result for the supplied test suite: 22 tests passed.
