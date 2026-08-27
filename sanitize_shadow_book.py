#!/usr/bin/env python3
import json
import os

BOOK = "shadow_book.json"


def load():
    if not os.path.exists(BOOK):
        return {"schema_version": 1, "signals": []}
    with open(BOOK, "r", encoding="utf-8") as f:
        return json.load(f)


def save(payload):
    with open(BOOK, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"))
        f.write("\n")


def main():
    book = load()
    signals = book.get("signals") or []
    cleaned = []
    seen_evergreen = set()
    removed = 0

    # Remove legacy patient-only conversion anomalies captured before
    # conversion freshness/execution validation was added.
    for s in signals:
        if s.get("engine") == "conversion" and (s.get("initial_patient_roi_pct") or 0) > 25:
            removed += 1
            continue
        cleaned.append(s)

    # Historical status churn can create two evergreen observations seconds apart
    # for the same item. Keep the earliest observation inside a 12h window.
    final = []
    for s in sorted(cleaned, key=lambda x: int(x.get("created_unix") or 0)):
        if s.get("engine") != "evergreen":
            final.append(s)
            continue
        item_id = s.get("item_id")
        created = int(s.get("created_unix") or 0)
        duplicate = False
        for prior_id, prior_created in seen_evergreen:
            if prior_id == item_id and abs(created - prior_created) <= 12 * 3600:
                duplicate = True
                break
        if duplicate:
            removed += 1
            continue
        seen_evergreen.add((item_id, created))
        final.append(s)

    book["signals"] = final
    save(book)
    print(f"Sanitized shadow book: removed={removed}, remaining={len(final)}")


if __name__ == "__main__":
    main()
