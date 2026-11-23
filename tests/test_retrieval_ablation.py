import math

from scripts import retrieval_ablation as ab


def hits(*titles):
    return [{"metadata": {"title": t}} for t in titles]


def test_rank_of_is_one_based_and_none_when_missing():
    assert ab.rank_of("B", hits("A", "B", "C")) == 2
    assert ab.rank_of("Z", hits("A", "B")) is None


def test_ndcg_with_one_right_document():
    assert ab.ndcg_at(1) == 1.0
    assert math.isclose(ab.ndcg_at(3), 0.5)
    assert ab.ndcg_at(11) == 0.0 and ab.ndcg_at(None) == 0.0


def test_summary_numbers():
    s = ab.summarize([1, 2, None, 5, 11], [10, 20, 30, 40, 50])
    assert s["recall@1"] == 0.2 and s["recall@3"] == 0.4 and s["recall@5"] == 0.6 and s["recall@10"] == 0.6
    assert math.isclose(s["mrr"], (1 + 0.5 + 0.2 + 1 / 11) / 5)
    assert s["not_found"] == 1 and s["p50_ms"] == 30


def test_percentile_edges():
    assert ab.percentile([], 95) == 0.0
    assert ab.percentile([5], 95) == 5
    assert ab.percentile(list(range(1, 101)), 95) == 95


def test_compare_counts_wins_losses_and_missing_as_worst():
    better, worse, same = ab.compare([1, 3, None, 2], [2, 1, 4, 2])
    assert (better, worse, same) == (2, 1, 1)
