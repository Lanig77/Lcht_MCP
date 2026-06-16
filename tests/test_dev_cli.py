import json

from lichtfeld_mcp import dev_cli


def test_dev_cli_emits_scene_api_flow(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["lichtfeld-mcp-dev", "demo_scene.lfp"])

    dev_cli.main()

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert len(payload) == 6
    assert payload[0]["name"] == "demo_scene"
    assert payload[1]["project_name"] == "demo_scene"
    assert payload[2]["selected_count"] > 0
    assert payload[5]["format"] == "spz"
