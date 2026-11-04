"""FP-Growth (Han, Pei and Yin 2000) with a measure switch.

standard: build the FP-tree from full baskets.
retained: build the FP-tree from kept baskets, so node counts are retained counts, then
compute the standard count of each output itemset from tid bitsets of the full baskets.
"""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations

import numpy as np

from rafim.measures import MEASURES, counts_for, is_frequent


class _Node:
    __slots__ = ("children", "count", "item", "parent")

    def __init__(self, item: int, parent: _Node | None):
        self.item = item
        self.count = 0
        self.parent = parent
        self.children: dict[int, _Node] = {}


class _Tree:
    """FP-tree with a header table of node lists per item."""

    def __init__(self, rank: dict[int, int]):
        self.root = _Node(-1, None)
        self.header: dict[int, list[_Node]] = defaultdict(list)
        self.item_count: dict[int, int] = defaultdict(int)
        self.rank = rank

    def insert(self, items: list[int], count: int) -> None:
        """Insert items (already in rank order) with a count."""
        node = self.root
        for it in items:
            child = node.children.get(it)
            if child is None:
                child = _Node(it, node)
                node.children[it] = child
                self.header[it].append(child)
            child.count += count
            self.item_count[it] += count
            node = child

    def single_path(self) -> list[_Node] | None:
        """Return the nodes of the tree if it is one path, else None."""
        path = []
        node = self.root
        while node.children:
            if len(node.children) > 1:
                return None
            node = next(iter(node.children.values()))
            path.append(node)
        return path


def _build(transactions, rank: dict[int, int], min_count_ok) -> _Tree:
    """Build a tree from (items, count) pairs, keeping only items that pass min_count_ok."""
    totals: dict[int, int] = defaultdict(int)
    for items, cnt in transactions:
        for it in items:
            totals[it] += cnt
    keep = {it for it, c in totals.items() if min_count_ok(c)}
    tree = _Tree(rank)
    for items, cnt in transactions:
        filtered = sorted((it for it in items if it in keep), key=rank.__getitem__)
        if filtered:
            tree.insert(filtered, cnt)
    return tree


def _mine(tree: _Tree, suffix: tuple, out: dict, min_count_ok, max_len) -> None:
    """Recursively mine a tree, writing {itemset: count} to out."""
    path = tree.single_path()
    if path is not None:
        for r in range(1, len(path) + 1):
            if max_len is not None and len(suffix) + r > max_len:
                break
            for combo in combinations(path, r):
                cnt = combo[-1].count  # deepest node has the smallest count
                if min_count_ok(cnt):
                    out[tuple(sorted(suffix + tuple(nd.item for nd in combo)))] = cnt
        return
    # Least frequent first.
    for it in sorted(tree.header, key=tree.rank.__getitem__, reverse=True):
        cnt = tree.item_count[it]
        if not min_count_ok(cnt):
            continue
        new = suffix + (it,)
        out[tuple(sorted(new))] = cnt
        if max_len is not None and len(new) >= max_len:
            continue
        base = []
        for node in tree.header[it]:
            items = []
            p = node.parent
            while p is not None and p.item != -1:
                items.append(p.item)
                p = p.parent
            if items:
                base.append((items[::-1], node.count))
        if base:
            cond = _build(base, tree.rank, min_count_ok)
            if cond.header:
                _mine(cond, new, out, min_count_ok, max_len)


def fpgrowth(full_lists: list[np.ndarray], kept_lists: list[np.ndarray] | None,
             full_bits: np.ndarray | None, n: int, minsup: float,
             measure: str = "standard", max_len: int | None = None) -> dict[tuple, tuple]:
    """Mine frequent itemsets with FP-Growth.

    Input: baskets as item-id arrays (full, and kept for retained), full-basket item
    bitsets (retained only, for the standard counts), n, minsup, measure, max_len.
    Output: {sorted item-id tuple: (full_count, kept_count or None)}.
    """
    if measure not in MEASURES:
        raise ValueError(measure)
    retained = measure == "retained"
    source = kept_lists if retained else full_lists

    def ok(c: int) -> bool:
        return bool(is_frequent(c, n, minsup))

    # Scan 1: item counts and rank (frequency descending, item id ascending).
    totals: dict[int, int] = defaultdict(int)
    for t in source:
        for it in t.tolist():
            totals[it] += 1
    freq = sorted((it for it, c in totals.items() if ok(c)), key=lambda it: (-totals[it], it))
    rank = {it: r for r, it in enumerate(freq)}
    # Scan 2: build the tree.
    tree = _build([(t.tolist(), 1) for t in source], rank, ok)
    found: dict[tuple, int] = {}
    _mine(tree, (), found, ok, max_len)
    if not retained:
        return {s: (c, None) for s, c in found.items()}
    std = counts_for(full_bits, found.keys())
    return {s: (std[s], c) for s, c in found.items()}
