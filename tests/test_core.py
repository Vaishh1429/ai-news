import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
import fetch

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)


def unit(*v):
    a = np.array(v, float)
    return a / np.linalg.norm(a)


def test_cluster_groups_similar_only():
    vecs = np.array([unit(1, 0), unit(0.99, 0.05), unit(0, 1)])
    assert fetch.cluster(vecs) == [0, 0, 1]


def test_summarize_strips_html_and_keeps_two_sentences():
    assert fetch.summarize("<p>One. Two! Three.</p>") == "One. Two!"


def test_merge_dedupes_and_expires():
    old = [fetch.item("a", "T", "http://x/1", NOW - timedelta(days=40))]
    new = [fetch.item("a", "T", "http://x/2", NOW)] * 2
    assert [i["url"] for i in fetch.merge(old, new, NOW)] == ["http://x/2"]


def test_story_lists_every_source():
    items = [fetch.item("A", "Launch", "u1", NOW), fetch.item("B", "Launch", "u2", NOW)]
    s = fetch.build_stories(items, [0, 0])
    assert len(s) == 1 and {x["name"] for x in s[0]["sources"]} == {"A", "B"}
