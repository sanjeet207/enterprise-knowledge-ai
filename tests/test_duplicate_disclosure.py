from app.services import ingest


def test_a_reader_is_told_which_document_already_holds_the_content():
    msg = ingest.duplicate_message({"title": "Travel Policy", "readable": True})
    assert "Travel Policy" in msg


def test_someone_who_cannot_read_it_learns_no_title():
    msg = ingest.duplicate_message({"title": "Project Titan Acquisition Valuation Memo", "readable": False})
    assert "Titan" not in msg and "already in the knowledge base" in msg


def test_a_missing_flag_fails_closed():
    assert "Secret" not in ingest.duplicate_message({"title": "Secret"})
