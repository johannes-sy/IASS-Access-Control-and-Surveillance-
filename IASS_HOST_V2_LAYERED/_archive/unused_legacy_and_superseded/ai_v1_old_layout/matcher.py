"""In-memory identity matcher with temporal-friendly confidence states."""
import cv2
import numpy as np

class FaceMatcher:
    def __init__(self, db, threshold=0.78, ambiguity_margin=0.04, embedder=None):
        self.db = db
        self.threshold = float(threshold)
        self.ambiguity_margin = float(ambiguity_margin)
        self.embedder = embedder
        self.index = {}
        self.people = {}
        self.refresh()

    def refresh(self):
        self.index = {}
        self.people = {p["id"]: p for p in self.db.list_people() if p.get("enabled", 1)}
        for sample in self.db.samples():
            pid = sample["person_id"]
            if pid not in self.people:
                continue
            arr = np.frombuffer(sample["image"], np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None:
                continue
            try:
                self.index.setdefault(pid, []).append(self.embedder.embed(img))
            except Exception:
                continue

    def match(self, crop):
        try:
            q = self.embedder.embed(crop)
        except Exception:
            return None, "UNKNOWN", 0.0, "LOW_CONFIDENCE"
        ranked = []
        for pid, vectors in self.index.items():
            # Average sample similarity gives robustness to a single poor enrollment image.
            scores = [float(np.dot(q, v)) for v in vectors]
            ranked.append((max(scores), pid))
        ranked.sort(reverse=True)
        if not ranked:
            return None, "UNKNOWN", 0.0, "UNKNOWN"
        best = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else -1.0
        if best[0] < self.threshold:
            return None, "UNKNOWN", best[0], "UNKNOWN"
        if len(ranked) > 1 and best[0] - second < self.ambiguity_margin:
            return None, "AMBIGUOUS", best[0], "AMBIGUOUS"
        person = self.people.get(best[1])
        if not person:
            return None, "UNKNOWN", best[0], "UNKNOWN"
        return person["id"], person["name"], best[0], "MATCHED"
