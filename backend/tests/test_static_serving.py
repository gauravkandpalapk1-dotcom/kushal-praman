"""Static frontend serving: Next.js segment-prefetch paths map onto the exported files."""
from backend.app.main import _segment_file


def test_segment_prefetch_paths_map_to_exported_files():
    assert _segment_file("login/__next.login.__PAGE__.txt") == "login/__next.login/__PAGE__.txt"
    assert (
        _segment_file("assessor/mapper/__next.assessor.mapper.__PAGE__.txt")
        == "assessor/mapper/__next.assessor/mapper/__PAGE__.txt"
    )


def test_non_segment_paths_are_untouched():
    assert _segment_file("__next._tree.txt") == "__next._tree.txt"
    assert _segment_file("index.html") == ""
    assert _segment_file("assessor/workspace") == ""


def test_static_serving_blocks_path_traversal(client):
    for path in ("/..%2f..%2f.env", "/%2e%2e/%2e%2e/backend/app/main.py", "/../../.env"):
        r = client.get(path)
        assert "JWT_SECRET" not in r.text and "create_app" not in r.text, path


def test_head_requests_are_served_for_ui_routes(client):
    # Next.js link prefetching probes routes with HEAD.
    assert client.head("/").status_code in (200, 404)
    assert client.head("/login").status_code != 405
