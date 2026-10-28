# IASS Host AI Architecture

## Responsibility boundary

```text
Camera -> AI perception -> semantic AI events
                         |
                         v
              SecurityScenarioEngine
                         |
                         v
                 HardwareIntent
                         |
                         v
                HardwareController
                         |
                         v
                ATmega transport
```

AI never decides GPIO actions, door unlocking, alarm activation, or serial commands.

## Pipeline

1. Face/person detection
2. Face quality gate
3. Face alignment/model boundary
4. In-memory identity embedding index
5. Identity matching
6. Persistent track association
7. Movement/direction estimation
8. Semantic event generation
9. Event delivery without blocking inference

## Recognition states

`MATCHED`, `UNKNOWN`, `AMBIGUOUS`, `LOW_CONFIDENCE`, `DISABLED`.

Recognition is not authorization. The security scenario layer uses the matched person and configured access level to make an access decision.

## Tracking

Each camera maintains persistent `TRACK-xxxxx` IDs. Recognition is associated with a track rather than repeated as a new security event on every frame. Track loss is delayed by a configurable missed-frame window.

`CrossCameraTrackManager` provides the host-side handoff registry for multi-camera deployments. It is intentionally independent of hardware.

## Performance

`AIWorker` uses a one-frame newest-wins queue. Camera/WebSocket handling never waits for inference, and inference never performs database writes synchronously.

Enrollment embeddings are cached in memory and refreshed after registration.

## Backend extensibility

The default embedding backend is a dependency-light OpenCV descriptor so the supplied project remains runnable without downloading a large neural model. The `FaceEmbedder` interface is the insertion point for an ONNX/YuNet/ArcFace/MobileFaceNet implementation when a model is supplied.

The detector interfaces are likewise replaceable without changing the event or hardware layers.
