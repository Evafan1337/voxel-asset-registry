"""Deterministic, opt-in structure checks for named component parts.

Pure Python by design: Blender supplies world AABBs, while this module tests their
relationships. Coordinates use glTF/Godot axes (X right, Y up, Z front), in metres.
AABB checks intentionally prove coarse contact/alignment, not physical stability.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class Box:
    name: str
    part: str
    lo: tuple[float, float, float]
    hi: tuple[float, float, float]

    def center(self, axis: int) -> float:
        return (self.lo[axis] + self.hi[axis]) / 2


_AXES = {"x": 0, "y": 1, "z": 2}
_EDGES = {"left": (0, 0), "right": (0, 1), "bottom": (1, 0),
          "top": (1, 1), "back": (2, 0), "front": (2, 1)}


def _issue(kind: str, objects: Sequence[str], message: str, **extra: Any) -> dict[str, Any]:
    return {"type": kind, "objects": list(objects), "message": message, **extra}


def _gap(a: Box, b: Box, axis: int) -> float:
    return max(0.0, a.lo[axis] - b.hi[axis], b.lo[axis] - a.hi[axis])


def _contact(a: Box, b: Box, tol: float) -> bool:
    return all(_gap(a, b, axis) <= tol for axis in range(3))


def _support(part: Box, support: Box, tol: float) -> bool:
    return (_gap(part, support, 0) <= tol and _gap(part, support, 2) <= tol
            and part.lo[1] - tol <= support.hi[1] <= part.hi[1] + tol)


def _edge(part: Box, target: Box, edge: str, tol: float) -> bool:
    axis, side = _EDGES[edge]
    plane = target.lo[axis] if side == 0 else target.hi[axis]
    if not (part.lo[axis] - tol <= plane <= part.hi[axis] + tol):
        return False
    if axis != 1 and _gap(part, target, 1) > tol:
        return False
    # A front/back edge is a horizontal line in X; a left/right edge is in Z.
    # Height may exceed the deck, but the part must contact it vertically.
    tangents = (0, 2) if axis == 1 else ((2,) if axis == 0 else (0,))
    return all(part.lo[a] >= target.lo[a] - tol and part.hi[a] <= target.hi[a] + tol
               for a in tangents)


def _mirrors(a: Box, b: Box, axis: int, origin: float, tol: float) -> bool:
    for i in range(3):
        expected_lo = 2 * origin - a.hi[i] if i == axis else a.lo[i]
        expected_hi = 2 * origin - a.lo[i] if i == axis else a.hi[i]
        if abs(expected_lo - b.lo[i]) > tol or abs(expected_hi - b.hi[i]) > tol:
            return False
    return True


def validate(intent: Mapping[str, Any] | None, boxes: Sequence[Box], level: int) -> dict[str, Any]:
    """Check semantic mesh groups; legacy components without intent are skipped."""
    if intent is None:
        return {"status": "skipped", "issues": [], "verified": [], "reason": "no design_intent"}

    primary = list(intent.get("primary_parts", []))
    secondary = list(intent.get("secondary_parts", []))
    declared = set(primary + secondary)
    grouped: dict[str, list[Box]] = {}
    issues: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    for box in boxes:
        if not box.part or box.part not in declared:
            issues.append(_issue("orphan_geometry", [box.name],
                                 f"mesh has no declared semantic_part: {box.part or '<unmarked>'}"))
        else:
            grouped.setdefault(box.part, []).append(box)
    for name in primary:
        if not grouped.get(name):
            issues.append(_issue("missing_primary_part", [name], f"primary part '{name}' has no mesh"))

    asymmetry = intent.get("intentional_asymmetry", {})
    for relation in intent.get("relationships", []):
        if level < relation.get("min_level", 0):
            continue
        kind = relation["type"]
        part_name = relation["part"]
        target_name = relation.get("target")
        source = grouped.get(part_name, [])
        target = grouped.get(target_name, []) if target_name else []
        tol = float(relation.get("tolerance", 0.015 if kind == "evenly_spaced" else 0.04))
        label = f"{kind}: {part_name}" + (f" -> {target_name}" if target_name else "")
        if kind in {"symmetric", "mirrored"} and part_name in asymmetry:
            verified.append({"relation": label, "status": "intentional_asymmetry",
                             "reason": asymmetry[part_name]})
            continue
        if not source or (target_name and not target):
            missing = part_name if not source else target_name
            issues.append(_issue("missing_relation_part", [str(missing)],
                                 f"{label}: referenced part has no mesh"))
            continue

        failed: list[str] = []
        if kind == "touches_ground":
            failed = [box.name for box in source if abs(box.lo[1]) > tol]
        elif kind in {"attached_to", "connected"}:
            failed = [box.name for box in source if not any(_contact(box, other, tol) for other in target)]
            if kind == "connected":
                failed += [box.name for box in target if not any(_contact(box, other, tol) for other in source)]
        elif kind == "supported_by":
            failed = [box.name for box in source if not any(_support(box, other, tol) for other in target)]
            # A nominal support that does not touch any supported part is decorative.
            failed += [box.name for box in target if not any(_support(other, box, tol) for other in source)]
        elif kind == "aligned":
            axis = _AXES[relation["axis"]]
            failed = [box.name for box in source
                      if not any(abs(box.center(axis) - other.center(axis)) <= tol for other in target)]
        elif kind == "contained_on_edge":
            failed = [box.name for box in source
                      if not any(_edge(box, other, relation["edge"], tol) for other in target)]
        elif kind == "evenly_spaced":
            if len(source) < 3:
                issues.append(_issue("insufficient_instances", [box.name for box in source],
                                     f"{label}: at least 3 instances are needed to test spacing"))
                continue
            spacing_axis = relation["axis"]
            if spacing_axis == "path":
                spans = [max(box.center(i) for box in source) - min(box.center(i) for box in source)
                         for i in range(3)]
                leading = max(range(3), key=lambda i: spans[i])
                order = sorted(source, key=lambda box: box.center(leading))
                centers = [tuple(box.center(i) for i in range(3)) for box in order]
                intervals = [math.dist(a, b) for a, b in zip(centers, centers[1:])]
                start, end = centers[0], centers[-1]
                direction = tuple(b - a for a, b in zip(start, end))
                length_sq = sum(value * value for value in direction)
                deviations = []
                for center in centers:
                    offset = tuple(value - origin for value, origin in zip(center, start))
                    fraction = sum(a * b for a, b in zip(offset, direction)) / length_sq if length_sq else 0.0
                    closest = tuple(origin + fraction * value for origin, value in zip(start, direction))
                    deviations.append(math.dist(center, closest))
                stray = max(deviations) > tol
            else:
                axis = _AXES[spacing_axis]
                order = sorted(source, key=lambda box: box.center(axis))
                centers = [box.center(axis) for box in order]
                intervals = [b - a for a, b in zip(centers, centers[1:])]
                # Small sideways offsets are as visible as uneven intervals.
                stray = any(max(box.center(other_axis) for box in order)
                            - min(box.center(other_axis) for box in order) > tol
                            for other_axis in range(3) if other_axis != axis)
            mean = sum(intervals) / len(intervals)
            if mean <= tol or any(abs(gap - mean) > tol for gap in intervals) or stray:
                failed = [box.name for box in order]
                issues.append(_issue("uneven_spacing", failed,
                                     f"{label}: centers={centers}, intervals={intervals}",
                                     axis=spacing_axis, intervals=[round(v, 5) for v in intervals]))
                continue
        elif kind in {"symmetric", "mirrored"}:
            axis = _AXES[relation["axis"]]
            origin = ((min(box.lo[axis] for box in target) + max(box.hi[axis] for box in target)) / 2
                      if target else 0.0)
            unmatched = set(range(len(source)))
            for i, box in enumerate(source):
                if i not in unmatched:
                    continue
                candidates = [j for j in unmatched if j != i and _mirrors(box, source[j], axis, origin, tol)]
                if candidates:
                    unmatched.remove(i)
                    unmatched.remove(candidates[0])
                elif _mirrors(box, box, axis, origin, tol):
                    unmatched.remove(i)
            if unmatched:
                issues.append(_issue("asymmetry", [source[i].name for i in sorted(unmatched)],
                                     f"{label}: no mirrored counterpart around {relation['axis']}={origin:.4f}"))
                continue
        if failed:
            issue_type = {"touches_ground": "floating_part", "supported_by": "unsupported",
                          "aligned": "misaligned", "contained_on_edge": "off_edge",
                          "attached_to": "detached", "connected": "disconnected"}.get(kind, kind)
            issues.append(_issue(issue_type, sorted(set(failed)), f"{label}: relation not satisfied"))
        else:
            verified.append({"relation": label, "status": "ok", "instances": len(source)})

    forbidden = set(intent.get("forbidden", []))
    if "floating_parts" in forbidden:
        # Coarse connected-to-ground proof across visible meshes. Contact may be
        # direct overlap or a narrow stylized joint; it is not a load solver.
        contact_tol = 0.04
        grounded = {i for i, box in enumerate(boxes) if abs(box.lo[1]) <= contact_tol}
        reachable = set(grounded)
        frontier = list(grounded)
        while frontier:
            i = frontier.pop()
            for j, other in enumerate(boxes):
                if j not in reachable and _contact(boxes[i], other, contact_tol):
                    reachable.add(j)
                    frontier.append(j)
        for i, box in enumerate(boxes):
            if i not in reachable:
                issues.append(_issue("floating_part", [box.name],
                                     "mesh has no AABB contact path to ground"))
    if "decorative_supports" in forbidden:
        support_targets = {relation.get("target") for relation in intent.get("relationships", [])
                           if relation["type"] == "supported_by" and level >= relation.get("min_level", 0)}
        for name in grouped:
            if "support" in name.lower() and name not in support_targets:
                issues.append(_issue("decorative_support", [box.name for box in grouped[name]],
                                     f"part '{name}' is called a support but supports no declared part"))
    limitations = []
    if "arbitrary_asymmetry" in forbidden:
        limitations.append("Only groups with an explicit symmetric/mirrored relation are tested for symmetry")

    return {"status": "fail" if issues else "ok", "issues": issues, "verified": verified,
            "parts": {name: len(group) for name, group in grouped.items()},
            "role": intent.get("role", ""), "purpose": intent.get("purpose", ""),
            "forbidden": sorted(forbidden), "limitations": limitations}
