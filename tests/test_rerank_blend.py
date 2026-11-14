from app.services.reranker import blend_order

# search positions in the reranker's order: position 0 (the search's first hit) was ranked 7th by the reranker
BY_RERANK = [3, 5, 1, 2, 4, 6, 0, 7]


def test_none_keeps_the_reranker_order():
    assert blend_order(BY_RERANK, "none", 5) == [3, 5, 1, 2, 4]


def test_guard_never_drops_the_first_search_hit():
    out = blend_order(BY_RERANK, "guard", 5)
    assert 0 in out and out[:4] == [3, 5, 1, 2] and len(out) == 5


def test_guard_changes_nothing_when_it_is_already_kept():
    assert blend_order([0, 2, 1, 3], "guard", 3) == [0, 2, 1]


def test_rrf_moves_a_search_favourite_up():
    out = blend_order([4, 3, 2, 1, 0], "rrf", 5)
    assert sorted(out) == [0, 1, 2, 3, 4] and out != [4, 3, 2, 1, 0]
    assert out.index(0) < 4  # strongest in search, last in rerank: lifted from last place


def test_empty_input():
    assert blend_order([], "guard", 5) == [] or blend_order([], "guard", 5) == [0]
