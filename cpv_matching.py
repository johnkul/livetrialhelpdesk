"""Deterministic, local CPV resolution. Similarity is evidence, not identity proof."""
from collections import Counter
from difflib import SequenceMatcher
from functools import lru_cache
import json
import unicodedata


def name_key(value):
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join("".join(c if c.isalnum() else " " for c in text).split())


def similarity(left, right):
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


class CPVMatcher:
    """Match only against a fixed roster; never learn from unreviewed predictions."""

    def __init__(self, established_aliases, config=None):
        config = config or {"schema_version": 1, "roster_additions": [], "aliases": {}}
        if not isinstance(config, dict) or config.get("schema_version") != 1:
            raise ValueError("CPV registry must use schema_version 1.")
        additions = config.get("roster_additions", [])
        overrides = config.get("aliases", {})
        if not isinstance(additions, list) or not all(isinstance(n, str) and name_key(n) for n in additions):
            raise ValueError("CPV roster_additions must be a list of names.")
        if not isinstance(overrides, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in overrides.items()):
            raise ValueError("CPV aliases must map names to established roster names.")
        self.roster = tuple(sorted(set(established_aliases.values()) | set(additions)))
        self.canonical = {name_key(n): n for n in self.roster}
        if len(self.canonical) != len(self.roster):
            raise ValueError("CPV roster contains duplicate normalized names.")
        self.aliases = {name_key(k): v for k, v in established_aliases.items()}
        for key, target in self.canonical.items():
            if key in self.aliases and self.aliases[key] != target:
                raise ValueError("A roster addition conflicts with a confirmed alias.")
            self.aliases[key] = target
        self.approved_keys = set()
        for raw, target in overrides.items():
            key = name_key(raw)
            if not key or target not in self.roster:
                raise ValueError("Each approved alias must have a name and an existing roster target.")
            if key in self.aliases and self.aliases[key] != target:
                raise ValueError("An approved alias conflicts with a confirmed mapping.")
            self.aliases[key] = target
            self.approved_keys.add(key)
        self.config = {"schema_version": 1, "roster_additions": sorted(set(additions)), "aliases": dict(overrides)}
        self.variants = tuple(self.aliases.items())

    @lru_cache(maxsize=8192)
    def resolve(self, raw):
        key = name_key(raw)
        original = str(raw or "").strip()
        if key in {"", "nan", "none", "missing", "not recorded", "na", "n a", "nat", "null"}:
            return ("[Not recorded]", "missing", 0.0, "")
        if key in self.aliases:
            method = "approved alias" if key in self.approved_keys else "confirmed"
            return (self.aliases[key], method, 1.0, "")

        tokens = key.split()
        # Exact rearrangements/spacing must resolve to ONE distinct person.
        exact = {target for variant, target in self.variants
                 if Counter(tokens) == Counter(variant.split()) or key.replace(" ", "") == variant.replace(" ", "")}
        if len(exact) == 1:
            return (next(iter(exact)), "name order / spacing", 1.0, "")
        if len(exact) > 1:
            return (original.title(), "ambiguous", 1.0, " | ".join(sorted(exact)))

        # Partial names are compared to the full roster, not one-word aliases.
        partial = {name for name in self.roster
                   if not (Counter(tokens) - Counter(name_key(name).split()))}
        if len(partial) == 1:
            return (next(iter(partial)), "unique partial name", 1.0, "")
        if len(partial) > 1:
            return (original.title(), "ambiguous", 1.0, " | ".join(sorted(partial)))

        scores = {}
        auto_scores = {}
        for variant, target in self.variants:
            other = variant.split()
            # A short nickname cannot anchor fuzzy automatic assignments.
            if len(variant.replace(" ", "")) < 6:
                continue
            compact = similarity(key.replace(" ", ""), variant.replace(" ", ""))
            sorted_score = similarity(" ".join(sorted(tokens)), " ".join(sorted(other)))
            score = max(compact, sorted_score)
            scores[target] = max(scores.get(target, 0), score)
            same_words = len(tokens) == len(other) and len(tokens) >= 2
            # Require every token to resemble a DISTINCT token (no subset score).
            remaining = list(other)
            token_scores = []
            if same_words:
                for token in sorted(tokens, key=len, reverse=True):
                    best = max(remaining, key=lambda x: similarity(token, x))
                    token_scores.append(similarity(token, best))
                    remaining.remove(best)
            full_name = same_words and min(token_scores) >= 0.72 and sum(token_scores) / len(tokens) >= 0.90
            joined_full_name = min(len(key.replace(" ", "")), len(variant.replace(" ", ""))) >= 10 and max(len(tokens), len(other)) >= 2 and compact >= 0.94
            if full_name or joined_full_name:
                auto_scores[target] = max(auto_scores.get(target, 0), score)

        ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
        if not ranked or ranked[0][1] < 0.65:
            return (original.title(), "unmatched", 0.0, "")
        best, score = ranked[0]
        runner_up = ranked[1][1] if len(ranked) > 1 else 0
        if auto_scores.get(best, 0) >= 0.90 and score - runner_up >= 0.12:
            return (best, "spelling match", round(score, 4), "")
        suggestions = " | ".join(name for name, value in ranked[:3] if value >= 0.65)
        return (original.title(), "needs review", round(score, 4), suggestions)

    def approved_config(self, draft):
        config = {**self.config, "aliases": {**self.config["aliases"], **draft}}
        # Revalidate every export, including clashes between normalized aliases.
        CPVMatcher(self.aliases, config)
        return json.dumps(config, ensure_ascii=False, indent=2) + "\n"
