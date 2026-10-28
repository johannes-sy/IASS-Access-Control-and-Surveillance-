# IASS Host V1 — AI / Interacting Layer Changes

## Preserved
- Existing UI and camera routes
- Existing database schema and hardware audit tables
- Existing hardware controller, registry, mock driver, ATmega transport/protocol
- Existing APIs and legacy modules
- Existing firmware integration contract

## Added / improved
- Modular AI detector, quality gate, embedding interface, matcher, tracker, pipeline and semantic events
- Persistent track IDs and movement direction
- Temporal track-based recognition instead of treating every frame as a new person
- In-memory enrollment embedding index
- Recognition states: MATCHED / UNKNOWN / AMBIGUOUS / LOW_CONFIDENCE
- Recognition/authorization separation
- Security scenario engine between AI and hardware
- Authorized-access scenario
- Unknown/suspicious/high-risk escalation
- Camera tracking through existing semantic hardware API
- Cross-camera track association support
- New AI/security configuration
- AI and integration documentation
- Additional unit tests

## Firmware
No ATmega328P firmware source was modified by this host-side change.
