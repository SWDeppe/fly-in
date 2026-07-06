from pathlib import Path

from src.orcestrator.runtime import build_framebuffers, parse_map_file, prepare_window, render_framebuffer_from_data


def test_parse_map_file() -> None:
    map_path = Path(__file__).resolve().parents[1] / "maps" / "easy" / "01_linear_path.txt"

    data = parse_map_file(map_path)

    assert data["nb_drones"] == 2
    assert data["start_hub"] == "start"
    assert data["end_hub"] == "goal"


def test_build_framebuffers() -> None:
    map_path = Path(__file__).resolve().parents[1] / "maps" / "easy" / "01_linear_path.txt"

    data = parse_map_file(map_path)
    framebuffers = build_framebuffers(data, width=160, height=120)

    assert set(framebuffers.keys()) == {"primary", "back"}
    assert framebuffers["primary"]["hub_count"] >= 1
    assert framebuffers["back"]["hub_count"] >= 1


def test_prepare_window_and_render_headless() -> None:
    map_path = Path(__file__).resolve().parents[1] / "maps" / "easy" / "01_linear_path.txt"

    data = prepare_window(map_path, width=160, height=120, create_window=False)
    primary = render_framebuffer_from_data("primary", data, create_window=False)
    back = render_framebuffer_from_data("back", data, create_window=False)

    assert primary["framebuffer"] == "primary"
    assert back["framebuffer"] == "back"
    assert primary["hub_count"] >= 1
