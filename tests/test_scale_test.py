from scripts import scale_test as st


def test_needles_are_deterministic_and_unique():
    a, b = st.make_needles(10, False, 1), st.make_needles(10, False, 1)
    assert [n["question"] for n in a] == [n["question"] for n in b]
    assert len({n["question"] for n in a}) == 10


def test_restricted_needles_are_level_four():
    assert all(n["level"] == st.RESTRICTED_LEVEL and n["restricted"] for n in st.make_needles(3, True, 1))
    assert all(n["level"] == st.VISIBLE_LEVEL for n in st.make_needles(3, False, 1))


def test_noise_has_three_children_and_some_restricted():
    docs = st.make_noise(200, seed=7)
    assert all(len(d["children"]) == 3 for d in docs)
    share = sum(d["restricted"] for d in docs) / len(docs)
    assert 0.15 < share < 0.45


def test_percentile():
    assert st.percentile([1, 2, 3, 4, 100], 95) == 100
    assert st.percentile([], 95) == 0.0
