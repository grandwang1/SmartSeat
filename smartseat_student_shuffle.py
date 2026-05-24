from __future__ import annotations

import random
from collections import defaultdict, deque


def disperse_group_order(students: list[dict], seed: int = 42) -> list[dict]:
    """
    Reorder students so no two consecutive entries share the same group_name.
    Uses greedy pick from largest remaining non-previous group bucket.
    """
    if not students:
        return []

    rng = random.Random(seed)
    buckets: dict[str, deque] = defaultdict(deque)
    for st in students:
        group = st.get("group_name") or st.get("group") or "未分組"
        buckets[group].append(st)

    for group in buckets:
        items = list(buckets[group])
        rng.shuffle(items)
        buckets[group] = deque(items)

    result: list[dict] = []
    prev_group: str | None = None

    while any(buckets[g] for g in buckets):
        candidates = [g for g in buckets if buckets[g] and g != prev_group]
        if not candidates:
            candidates = [g for g in buckets if buckets[g]]
        group = max(candidates, key=lambda g: len(buckets[g]))
        student = buckets[group].popleft()
        result.append(student)
        prev_group = group

    return result
