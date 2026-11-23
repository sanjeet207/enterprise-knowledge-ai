from app.services.answer_check import repair_neighbor_citation, uncited_sentences

P = ["Expense claims must be submitted within 30 days of the end of the trip. Claims submitted later are paid only with the approval of the finance controller.",
     "Leave in Singapore is 18 days."]


def test_neighbor_sentence_in_the_cited_passage_takes_the_citation():
    a = "Claims are due within 30 days of the trip [1]. Claims submitted later are paid only with the approval of the finance controller."
    fixed = repair_neighbor_citation(a, P)
    assert fixed.endswith("finance controller [1].")
    assert uncited_sentences(fixed, 2) == []


def test_neighbor_sentence_not_in_the_cited_passage_stays_uncited():
    a = "Claims are due within 30 days of the trip [1]. Directors may approve any hotel limit without a receipt."
    assert repair_neighbor_citation(a, P) == a
    assert len(uncited_sentences(a, 2)) == 1


def test_sentence_after_an_uncited_sentence_is_not_repaired_without_a_cited_neighbor():
    a = "Claims are due within 30 days. Claims submitted later are paid only with the approval of the finance controller."
    assert repair_neighbor_citation(a, P) == a


def test_scope_lead_in_before_a_cited_sentence_is_allowed():
    a = "This depends on your location and role. In Singapore, employees receive 18 days of leave [2]."
    assert uncited_sentences(a, 2) == []


def test_scope_lead_in_with_a_figure_or_without_cited_next_is_not_allowed():
    assert uncited_sentences("This depends on your role and is usually 18 days. In Singapore it is 18 days [2].", 2)
    assert uncited_sentences("This depends on your location and role. In Singapore it is 18 days.", 2)


def test_scope_wording_later_in_the_answer_is_not_allowed():
    a = "In Singapore, employees receive 18 days of leave [2]. Both documents provide different timelines, but the stricter one should be followed."
    assert uncited_sentences(a, 2)
