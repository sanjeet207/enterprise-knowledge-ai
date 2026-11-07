import pytest

from app.services import extract


def test_plain_text_is_read_and_trimmed():
    assert extract.extract_text("policy.txt", b"  Leave is 24 days.  \r\nSecond line \n") == "Leave is 24 days.\nSecond line"


def test_markdown_and_csv_are_accepted():
    assert extract.extract_text("a.md", b"# Title\ntext")
    assert extract.extract_text("a.CSV", b"a,b\n1,2")


def test_unsupported_type_is_refused():
    with pytest.raises(extract.ExtractError, match="Unsupported"):
        extract.extract_text("virus.exe", b"MZ")


def test_empty_file_is_refused():
    with pytest.raises(extract.ExtractError, match="empty"):
        extract.extract_text("a.txt", b"")


def test_whitespace_only_has_no_text():
    with pytest.raises(extract.ExtractError, match="No readable text"):
        extract.extract_text("a.txt", b"   \n  ")


def test_oversized_file_is_refused():
    with pytest.raises(extract.ExtractError, match="5 MB"):
        extract.extract_text("a.txt", b"a" * (extract.MAX_BYTES + 1))


def test_too_much_text_is_refused():
    with pytest.raises(extract.ExtractError, match="too much text"):
        extract.extract_text("a.txt", b"a" * (extract.MAX_CHARS + 1))


def test_binary_renamed_to_txt_is_refused():
    with pytest.raises(extract.ExtractError, match="text file"):
        extract.extract_text("a.txt", b"abc\x00\x01\x02")


def test_fake_pdf_and_docx_are_refused_before_any_reader_runs():
    with pytest.raises(extract.ExtractError, match="valid PDF"):
        extract.extract_text("a.pdf", b"not a pdf")
    with pytest.raises(extract.ExtractError, match="valid Word"):
        extract.extract_text("a.docx", b"not a zip")


def test_word_document_round_trip():
    docx = pytest.importorskip("docx")
    import io
    document = docx.Document()
    document.add_paragraph("Annual leave is twenty-four days.")
    table = document.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Grade"
    table.rows[0].cells[1].text = "Manager"
    buffer = io.BytesIO()
    document.save(buffer)
    text = extract.extract_text("leave.docx", buffer.getvalue())
    assert "twenty-four days" in text and "Grade | Manager" in text
