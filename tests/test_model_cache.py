"""The reranker model cache: stored permanently, and repaired when the model file is missing."""
from pathlib import Path

from app.services import model_cache

MODEL = "ms-marco-MiniLM-L-12-v2"


def test_default_cache_is_in_the_home_folder_not_tmp(monkeypatch):
    monkeypatch.delenv("FLASHRANK_CACHE_DIR", raising=False)
    path = model_cache.cache_dir()
    assert path.startswith(str(Path.home())) and not path.startswith("/tmp")


def test_cache_dir_can_be_set_by_environment(monkeypatch):
    monkeypatch.setenv("FLASHRANK_CACHE_DIR", "/opt/flashrank-cache")
    assert model_cache.cache_dir() == "/opt/flashrank-cache"


def test_missing_cache_is_created(tmp_path):
    target = tmp_path / "new" / "cache"
    assert model_cache.prepare(str(target), MODEL) == str(target)
    assert target.is_dir()


def test_empty_model_folder_is_removed_so_it_downloads_again(tmp_path):
    (tmp_path / MODEL).mkdir()  # what a cleaned /tmp left behind: the folder, no model file
    model_cache.prepare(str(tmp_path), MODEL)
    assert not (tmp_path / MODEL).exists()


def test_model_folder_with_other_files_but_no_model_is_removed(tmp_path):
    folder = tmp_path / MODEL
    folder.mkdir()
    (folder / "config.json").write_text("{}")
    model_cache.prepare(str(tmp_path), MODEL)
    assert not folder.exists()


def test_a_good_model_folder_is_left_alone(tmp_path):
    folder = tmp_path / MODEL
    folder.mkdir()
    (folder / "flashrank-MiniLM-L-12-v2_Q.onnx").write_bytes(b"model")
    model_cache.prepare(str(tmp_path), MODEL)
    assert (folder / "flashrank-MiniLM-L-12-v2_Q.onnx").read_bytes() == b"model"
