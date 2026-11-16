from app.services.answer_check import (accept_refinement, annotate_number_words, repair_lead_citation,
                                       strip_number_annotations)


def test_number_words_get_digits():
    assert annotate_number_words("above twenty-five lakh rupees") == "above twenty-five (25) lakh rupees"
    assert annotate_number_words("within thirty days") == "within thirty (30) days"
    assert annotate_number_words("up to ten unused days") == "up to ten (10) unused days"
    assert annotate_number_words("three days a week") == "three (3) days a week"


def test_one_and_plain_text_are_left_alone():
    assert annotate_number_words("one hour, and none of them") == "one hour, and none of them"


def test_no_double_annotation():
    assert annotate_number_words("thirty (30) days") == "thirty (30) days"


def test_lead_verdict_takes_the_next_citation():
    a = "No, you cannot work on customer records from your personal Google Drive. Customer data may not be copied to personal cloud storage [1]."
    out = repair_lead_citation(a, 1)
    assert out.startswith("No, you cannot work on customer records from your personal Google Drive [1].")


def test_other_uncited_sentences_are_not_repaired():
    a = "Executive pay has two parts. The variable part is linked to revenue [1]."
    assert repair_lead_citation(a, 1) == a


def test_already_cited_lead_is_unchanged():
    a = "Yes [1]. It is allowed [1]."
    assert repair_lead_citation(a, 1) == a


def test_search_rewrite_may_reword_but_not_change_numbers():
    q = "how many holidays do we get in a year and can some of them be rolled over"
    r = "How many days of annual leave do employees get each year and can unused leave be carried forward?"
    assert accept_refinement(q, r) == q                       # strict default refuses a synonym rewrite
    assert accept_refinement(q, r, min_overlap=0.4) == r      # the search-only setting accepts it
    assert accept_refinement("leave for 5 days", "Annual leave for 7 days", min_overlap=0.4) == "leave for 5 days"


def test_annotations_are_stripped_from_answers():
    assert strip_number_annotations("Contracts above twenty-five (25) lakh rupees need director approval [1].") == \
        "Contracts above twenty-five lakh rupees need director approval [1]."
    assert strip_number_annotations("thirty (30) minutes") == "thirty minutes"
    assert strip_number_annotations("The limit is 30 days (see policy).") == "The limit is 30 days (see policy)."


def test_annotate_then_strip_gives_back_the_original():
    text = "Employees receive twenty-four days; up to ten unused days carry forward within thirty days of travel."
    assert strip_number_annotations(annotate_number_words(text)) == text


def test_conclusion_sentence_takes_citation_of_sentence_it_restates():
    from app.services.answer_check import repair_conclusion_citation, uncited_sentences
    a = ("Purchases above five lakh rupees require at least three written quotations [1]. "
         "Since the purchase is for 6 lakh rupees, you need to collect at least three written quotations.")
    fixed = repair_conclusion_citation(a, 1)
    assert fixed.endswith("quotations [1].") and not uncited_sentences(fixed, 1)


def test_unrelated_uncited_sentence_is_not_repaired():
    from app.services.answer_check import repair_conclusion_citation, uncited_sentences
    a = "Leave requests need manager approval [1]. Employees must use multi-factor authentication everywhere."
    assert uncited_sentences(repair_conclusion_citation(a, 1), 1)
