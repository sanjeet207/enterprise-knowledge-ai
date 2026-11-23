import csv
import io

from app.services import audit_export as ax


def parse(text):
    return list(csv.reader(io.StringIO(text)))


def test_header_and_a_normal_row():
    rows = parse(ax.to_csv([{"created_at": "2026-11-23", "user_email": "a@acme.test", "role_level": 1,
                             "query": "How many leave days?", "outcome": "answered", "top_score": 0.9,
                             "latency_ms": 1200, "model": "ollama:qwen2.5:7b"}]))
    assert rows[0] == list(ax.COLUMNS)
    assert rows[1][3] == "How many leave days?" and rows[1][4] == "answered"


def test_a_question_cannot_run_as_a_spreadsheet_formula():
    rows = parse(ax.to_csv([{"query": '=HYPERLINK("http://evil","x")', "user_email": "@x", "outcome": "-1+1"}]))
    assert rows[1][3].startswith("'=") and rows[1][1].startswith("'@") and rows[1][4].startswith("'-")


def test_commas_quotes_and_newlines_stay_in_one_cell():
    rows = parse(ax.to_csv([{"query": 'a, "b"\nc'}]))
    assert len(rows) == 2 and rows[1][3] == 'a, "b"\nc'


def test_the_file_never_carries_answers_or_passages():
    assert "answer" not in ax.COLUMNS and "sources" not in ax.COLUMNS
    text = ax.to_csv([{"query": "q", "answer": "SECRET SALARY", "sources": [{"excerpt": "SECRET"}]}])
    assert "SECRET" not in text


def test_export_route_needs_partner_level():
    from app.main import app
    route = next(r for r in app.routes if getattr(r, "path", "") == "/audit/export.csv")
    assert "GET" in route.methods and len(route.dependant.dependencies) >= 1
