# AI perception upgrade (consolidated)

This covers two rounds of changes to `ai_perception/`, both now fully
merged into this codebase (previously the detector swap was only handed
over as a separate `IASS_AI_UPGRADE.zip`; it's now part of this project,
carried through the architecture migration and verified again here).
Only `detector.py` and `embedder.py` changed. Nothing else in the pipeline
(`pipeline.py`, `tracker.py`, `matcher.py`, `quality.py`, `models.py`)
needed to change either time -- both classes kept their exact public
interface.

## Round 1: detection (Haar cascade + HOG -> YOLOv11 ONNX)

- `models/yolov11n-face.onnx` -- face detector trained on WIDERFace
  (github.com/akanametov/yolo-face, release 1.0.0). Replaces
  `cv2.CascadeClassifier` for faces.
- `models/yolo11n.onnx` -- general 80-class COCO detector, filtered to
  class 0 (person) (github.com/ultralytics/assets, release v8.3.0).
  Replaces `cv2.HOGDescriptor` for bodies.
- Automatic fallback to the old Haar/HOG behavior if `onnxruntime` or a
  model file is missing -- check `detector.kind` at runtime to see which
  backend is actually active.

## Round 2: recognition (handcrafted descriptor -> real ArcFace)

This is the part that decides *who* a face belongs to, not just *that*
there's a face -- and it was the weakest link even after Round 1, because
`OpenCVFeatureEmbedder` was a handcrafted intensity+gradient descriptor,
not a trained recognition network.

- `models/arcface_w600k_r50.onnx` -- a real ArcFace (ResNet50, trained on
  WebFace600K) face recognition network, downloaded from InsightFace's
  official release (github.com/deepinsight/insightface, release v0.7,
  `buffalo_l.zip` -> `w600k_r50.onnx`). This is the same recognition model
  InsightFace's own production bundle uses -- an industry-standard
  architecture, not an approximation. Produces a 512-d embedding.
- Unlike the SFace option from Round 1 (still available, see
  `embedder.py`'s docstring), this one **is bundled in `models/`** because
  it's a plain GitHub release asset rather than Git LFS, so this sandbox's
  network allowlist could actually reach it.
- `ai_embedding_backend` default changed from `"opencv"` to `"arcface"` in
  both `config/settings.py` and `config/v1.toml`.
- `recognition_threshold` default changed from `0.78` to `0.38` to match --
  ArcFace's cosine similarities live on a different scale than the old
  handcrafted descriptor's. **If you have an existing deployment with a
  hand-tuned `recognition_threshold`, re-check it** rather than trusting
  the new default blindly; 0.38 is a reasonable starting point for
  buffalo_l, not a guarantee for your specific camera/lighting conditions.
- Falls through automatically: `arcface` -> `sface` -> handcrafted
  descriptor, in that order, if a model or `onnxruntime` isn't available --
  nothing crashes for lack of a model, it just degrades.

### Known limitation, flagged rather than hidden

ArcFace's accuracy depends on feeding it a consistently, tightly aligned
face crop. Right now the pipeline feeds it the plain bounding-box crop from
the YOLO face detector -- no landmark-based alignment. InsightFace's own
pipeline pairs this recognition model with a detector (RetinaFace,
`det_10g.onnx`, also present in the same release) that emits 5-point
landmarks used to warp each face into a canonical pose first. I downloaded
`det_10g.onnx` but did not wire it in -- decoding RetinaFace's
multi-scale anchor output correctly is a meaningfully larger piece of work
than the YOLO decode, and unaligned ArcFace crops still perform well above
the handcrafted descriptor, so I made the call to ship the recognition
upgrade now rather than block it on a second detector rewrite. This is the
next real lever if you want to close the remaining accuracy gap.

### Performance, measured honestly

In this sandbox (shared, throttled CPU, not representative of your
deployment hardware): ArcFace inference is ~290ms per face crop, warm.
`matcher.match()` calls this for *every* quality-accepted face on *every*
processed frame (already throttled by `process_every_n_frames`), not just
once per new track -- so cost scales with faces-in-frame x processed-frames.
On real hardware this will be faster, but it's still a meaningfully heavier
model than the face detector. If this turns out to be a bottleneck on your
target hardware, the next lever isn't a smaller model, it's caching: only
re-embed a track once it's newly created or its quality score improves,
rather than on every frame it's already confidently matched on -- that's an
architecture change to `pipeline.py`/`tracker.py`, not attempted here.

## Verified

- `pytest` -- 28/28 pass
- `iass.api.app.create_app()` boots clean, 53 routes
- `build_embedder("arcface")` loads the real model, produces a
  deterministic, L2-normalized 512-d vector
- `FaceDetector`/`PersonDetector` `.kind` confirms YOLO backends are active,
  not the Haar/HOG fallback

## Requirements

`onnxruntime>=1.18,<2` (already added to `requirements.txt` in Round 1).
