#!/usr/bin/env python3
"""Serialization smoke gate (added 11.0.1, after the on-device crash
'TypeError: can not serialize set object' — Flet's Android msgpack
bridge packs control property values raw; a Python set in any control
field kills the app at page.add).

Builds the app's real startup tree on the harness FakePage and fails
if any control field value is, or contains, a set/frozenset. Includes
a self-test: a SegmentedButton carrying selected={...} MUST be flagged,
proving the scanner can see the failure class it guards.
"""
import dataclasses
import sys

import flet as ft

from harness import FakePage, walk
import main as app


def find_sets(value, path, hits, depth=0):
    if depth > 12:
        return
    if isinstance(value, (set, frozenset)):
        hits.append(path)
        return
    if isinstance(value, dict):
        for k, v in value.items():
            find_sets(v, f"{path}.{k}", hits, depth + 1)
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            find_sets(v, f"{path}[{i}]", hits, depth + 1)
    elif dataclasses.is_dataclass(value) and not isinstance(value, type):
        for f in dataclasses.fields(value):
            try:
                v = getattr(value, f.name)
            except Exception:
                continue
            find_sets(v, f"{path}.{f.name}", hits, depth + 1)


def scan(roots):
    hits = []
    seen = 0
    for root in roots:
        for ctrl in walk(root):
            seen += 1
            if dataclasses.is_dataclass(ctrl) and not isinstance(ctrl, type):
                for f in dataclasses.fields(ctrl):
                    try:
                        v = getattr(ctrl, f.name)
                    except Exception:
                        continue
                    find_sets(v, f"{type(ctrl).__name__}.{f.name}", hits)
    return seen, hits


def main():
    # Self-test: the pre-fix construction must be caught.
    bad = ft.SegmentedButton(
        segments=[ft.Segment(value="all", label=ft.Text("All"))],
        selected={"all"})
    _, self_hits = scan([bad])
    assert self_hits, "SELF-TEST FAILED: scanner missed a known set"

    page = FakePage()
    app.main(page)
    roots = list(page.controls)
    if page.navigation_bar is not None:
        roots.append(page.navigation_bar)
    seen, hits = scan(roots)
    if hits:
        print(f"FAIL: {len(hits)} set-valued control field(s):")
        for h in hits[:10]:
            print("  ", h)
        return 1
    print(f"PASS: {seen} controls scanned, no set-valued fields "
          f"(self-test tripped on {len(self_hits)} known set)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
