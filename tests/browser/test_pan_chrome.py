"""Chrome-family Playwright interaction regression on the standalone Pan contract fixture.

This is NOT a post-build verification of deployed upstream n8n.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[2]


def drag(page, start, end, button="left", steps=8):
    page.mouse.move(*start)
    page.mouse.down(button=button)
    page.mouse.move(*end, steps=steps)
    page.mouse.up(button=button)


def main():
    results = {}
    with sync_playwright() as p:
        chrome = os.environ.get("CHROME_PATH") or shutil.which("chromium")
        launch_options = {"headless": True, "args": ["--no-sandbox"]}
        if chrome:
            launch_options["executable_path"] = chrome
        browser = p.chromium.launch(**launch_options)
        page = browser.new_page(viewport={"width": 1440, "height": 920}, device_scale_factor=1)
        html = (ROOT / "tests/browser/pan_harness.html").read_text(encoding="utf8")
        contract = (ROOT / "packages/pan/pan-contract.mjs").read_text(encoding="utf8").replace(
            "export const CANVAS_PAN", "const CANVAS_PAN"
        )
        html = html.replace("import { CANVAS_PAN } from '../../packages/pan/pan-contract.mjs';", contract)
        page.set_content(html)
        page.get_by_test_id("pane").wait_for()
        state = lambda: page.evaluate("window.getCanvasState()")
        pane = page.get_by_test_id("pane").bounding_box()
        ox, oy = pane["x"], pane["y"]
        def pt(x, y):
            return (ox + x, oy + y)

        before = state()
        drag(page, pt(740, 520), pt(865, 600))
        after = state()
        assert round(after["offset"]["x"] - before["offset"]["x"]) == 125, after
        assert round(after["offset"]["y"] - before["offset"]["y"]) == 80, after
        results["left_pane_pan"] = "PASS"

        drag(page, pt(700, 520), pt(625, 480), "middle")
        after2 = state()
        assert round(after2["offset"]["x"] - after["offset"]["x"]) == -75, after2
        assert round(after2["offset"]["y"] - after["offset"]["y"]) == -40, after2
        results["middle_pane_pan"] = "PASS"

        current = state()
        page.keyboard.down("Shift")
        drag(page, pt(100, 100), pt(520, 350))
        page.keyboard.up("Shift")
        chosen = state()
        assert chosen["offset"] == current["offset"], chosen
        assert "n1" in chosen["selected"], chosen
        results["shift_drag_range_selection"] = "PASS"

        n1 = next(n for n in chosen["nodes"] if n["id"] == "n1")
        a = pt(n1["x"] + chosen["offset"]["x"] + 50, n1["y"] + chosen["offset"]["y"] + 35)
        drag(page, a, (a[0] + 120, a[1] + 60))
        moved = state()
        n1after = next(n for n in moved["nodes"] if n["id"] == "n1")
        assert round(n1after["x"] - n1["x"]) == 120, moved
        assert round(n1after["y"] - n1["y"]) == 60, moved
        assert moved["offset"] == chosen["offset"], moved
        results["node_drag_is_not_pan"] = "PASS"

        src = page.locator('[data-source="n1"]').bounding_box()
        dst = page.locator('[data-target="n2"]').bounding_box()
        drag(page,
            (src["x"] + src["width"]/2, src["y"] + src["height"]/2),
            (dst["x"] + dst["width"]/2, dst["y"] + dst["height"]/2))
        assert len(state()["edges"]) == 1, state()
        assert state()["offset"] == chosen["offset"], state()
        results["handle_drag_connection"] = "PASS"

        page.get_by_role("button", name="노드 추가").click()
        assert len(state()["nodes"]) == 3, state()
        results["add_node"] = "PASS"

        page.locator('[data-node-id="n3"]').click(position={"x": 115, "y": 20})
        assert "n3" in state()["selected"], state()
        page.get_by_role("button", name="선택 노드 삭제").click()
        assert len(state()["nodes"]) == 2, state()
        results["delete_selected_node"] = "PASS"

        page.mouse.move(*pt(740, 550))
        page.mouse.wheel(0, -210)
        assert state()["zoom"] > 1, state()
        results["wheel_zoom"] = "PASS"

        page.screenshot(path=str(ROOT / "tests/browser/chrome-pan-proof.png"), full_page=True)
        (ROOT / "tests/browser/chrome-test-results.json").write_text(
            json.dumps({"results": results, "chrome_user_interaction": True,
                        "scope": "local_contract_fixture_not_upstream_n8n"},
                       ensure_ascii=False, indent=2), encoding="utf8")
        browser.close()
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
