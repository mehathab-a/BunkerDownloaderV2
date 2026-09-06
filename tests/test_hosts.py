"""Unit tests for multi-host resolvers (mocked HTTP)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.hosts import resolve_url, supported_hosts
from src.hosts.cyberdrop import CyberdropResolver
from src.hosts.gofile import GofileResolver
from src.hosts.pixeldrain import PixeldrainResolver
from src.hosts.saint import SaintResolver


def test_supported_hosts() -> None:
    assert supported_hosts() == ["pixeldrain", "gofile", "cyberdrop", "saint"]


def test_pixeldrain_file() -> None:
    resolver = PixeldrainResolver()
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {"name": "hello.txt", "size": 42}
    with patch("src.hosts.pixeldrain.http_client.get", return_value=fake):
        items = resolver.resolve("https://pixeldrain.com/u/AbC123")
    assert len(items) == 1
    assert items[0].filename == "hello.txt"
    assert items[0].download_url.endswith("/file/AbC123?download")


def test_pixeldrain_list() -> None:
    resolver = PixeldrainResolver()
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {
        "files": [
            {"id": "f1", "name": "a.bin", "size": 1},
            {"id": "f2", "name": "b.bin", "size": 2},
        ],
    }
    with patch("src.hosts.pixeldrain.http_client.get", return_value=fake):
        items = resolver.resolve("https://pixeldrain.com/l/LIST1")
    assert [item.filename for item in items] == ["a.bin", "b.bin"]


def test_gofile() -> None:
    resolver = GofileResolver()
    with (
        patch.object(resolver, "_create_guest_token", return_value="tok"),
        patch.object(resolver, "_discover_website_token", return_value="wt123"),
        patch.object(
            resolver,
            "_fetch_contents",
            return_value={
                "1": {
                    "type": "file",
                    "name": "pic.jpg",
                    "link": "https://store1.gofile.io/download/x/pic.jpg",
                    "size": 9,
                },
                "2": {"type": "folder"},
            },
        ),
    ):
        items = resolver.resolve("https://gofile.io/d/CODE1")
    assert len(items) == 1
    assert items[0].filename == "pic.jpg"
    assert "accountToken=tok" in items[0].headers["Cookie"]


def test_cyberdrop_album() -> None:
    resolver = CyberdropResolver()
    album_html = MagicMock()
    album_html.raise_for_status = MagicMock()
    album_html.text = (
        '<a id="file" href="/f/fileAAA"></a>'
        '<a id="file" href="/f/fileBBB"></a>'
    )
    info = MagicMock()
    info.raise_for_status = MagicMock()
    info.json.side_effect = [
        {
            "name": "one.png",
            "size": 10,
            "auth_url": "https://api.cyberdrop.cr/api/file/auth/fileAAA",
        },
        {"url": "https://cdn.example/one.png"},
        {
            "name": "two.png",
            "size": 20,
            "auth_url": "https://api.cyberdrop.cr/api/file/auth/fileBBB",
        },
        {"url": "https://cdn.example/two.png"},
    ]
    with patch(
        "src.hosts.cyberdrop.http_client.get",
        side_effect=[album_html, info, info, info, info],
    ):
        items = resolver.resolve("https://cyberdrop.cr/a/ALB1")
    assert [item.filename for item in items] == ["one.png", "two.png"]


def test_saint() -> None:
    resolver = SaintResolver()
    page = MagicMock()
    page.raise_for_status = MagicMock()
    page.text = (
        '<video id="main-video">'
        '<source src="https://simp2.saint2.su/videos/clip.mp4">'
        "</video>"
    )
    with patch("src.hosts.saint.http_client.get", return_value=page):
        items = resolver.resolve("https://saint2.su/embed/vid1")
    assert items[0].filename == "clip.mp4"


def test_dispatch() -> None:
    fake = MagicMock()
    fake.raise_for_status = MagicMock()
    fake.json.return_value = {"name": "z.txt", "size": 1}
    with patch("src.hosts.pixeldrain.http_client.get", return_value=fake):
        host, items = resolve_url("https://pixeldrain.com/u/AbC123")
    assert host == "pixeldrain"
    assert items[0].filename == "z.txt"


if __name__ == "__main__":
    test_supported_hosts()
    test_pixeldrain_file()
    test_pixeldrain_list()
    test_gofile()
    test_cyberdrop_album()
    test_saint()
    test_dispatch()
    print("ALL MOCK TESTS PASSED")
