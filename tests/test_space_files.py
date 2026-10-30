"""The Space's own files (space/) must describe the environment the numbers were measured in.

The Space installs `space/requirements.txt`, not the lock, and its Gradio comes from `sdk_version`
in `space/README.md`. Without a check, the lock can move and the Space keep the old versions, or a
version typed into the README can differ from the one every test ran on. The declared differences
are listed here once, with their reasons in the header of `space/requirements.txt`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SPACE = ROOT / "space"
sys.path.insert(0, str(ROOT / "src"))

#: Installed by the Space itself at `sdk_version`; the README test ties that version to the lock.
LEFT_TO_THE_SPACE = {"gradio"}
#: The Space installs `gradio[oauth,mcp]` in the same pip command, and its mcp extra caps pydantic
#: (difference 3 in the header of space/requirements.txt, with the measurement behind it).
HELD_BY_THE_SPACE = {"pydantic": "2.12.5", "pydantic-core": "2.41.5"}


def _lines(path: Path) -> list[str]:
    return [l.strip() for l in path.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#")]


def _pins(path: Path) -> dict[str, str]:
    """name ⇒ version for `name==version`, and name ⇒ the URL for a direct reference `name @ URL`."""
    out: dict[str, str] = {}
    for line in _lines(path):
        name, sep, rest = line.partition(" @ ") if " @ " in line else line.partition("==")
        assert sep, f"سطرٌ غيرُ مثبَّت: {line}"
        out[name.lower().replace("_", "-")] = rest
    return out


def _front_matter() -> dict:
    text = (SPACE / "README.md").read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert m, "space/README.md بلا ترويسة YAML: الـSpace لا يُبنى بدونها"
    return yaml.safe_load(m.group(1))


def test_the_space_installs_the_lock_with_only_the_declared_differences():
    lock = _pins(ROOT / "requirements.lock")
    space = _pins(SPACE / "requirements.txt")
    expected = {name: version for name, version in lock.items()
                if name not in LEFT_TO_THE_SPACE and name != "torch"} | HELD_BY_THE_SPACE
    rest = {name: version for name, version in space.items() if name != "torch"}
    assert rest == expected, (
        "space/requirements.txt انزاح عن requirements.lock: "
        f"زائد {sorted(set(rest) - set(expected))} · ناقص {sorted(set(expected) - set(rest))} · "
        f"مختلف {sorted(n for n in set(rest) & set(expected) if rest[n] != expected[n])}")


def test_torch_is_the_cpu_wheel_of_the_locked_release_for_the_space_python():
    url = _pins(SPACE / "requirements.txt")["torch"]
    release = _pins(ROOT / "requirements.lock")["torch"]
    py = str(_front_matter()["python_version"]).replace(".", "")
    assert url.startswith("https://download-r2.pytorch.org/whl/cpu/"), url
    assert f"/torch-{release}%2Bcpu-cp{py}-cp{py}-manylinux" in url, (
        f"عجلةُ torch ليست نسخةَ القفل {release} للمعالج المركزيّ ولـPython {py}: {url}")
    assert re.search(r"#sha256=[0-9a-f]{64}$", url), "العجلةُ بلا بصمة sha256"


def test_nothing_reaches_the_installer_but_pins():
    options = [l for l in _lines(SPACE / "requirements.txt") if l.startswith("-")]
    assert options == [], f"خياراتُ تثبيتٍ غيرُ معلنة: {options}"


def test_the_space_gradio_is_the_locked_gradio():
    meta = _front_matter()
    assert meta["sdk"] == "gradio"
    assert str(meta["sdk_version"]) == _pins(ROOT / "requirements.lock")["gradio"]
    assert (ROOT / meta["app_file"]).is_file()


def test_the_retrieval_model_is_preloaded_at_build_time():
    from statement_qa.retriever import EMBED_MODEL

    preloaded = [item.split()[0] for item in _front_matter().get("preload_from_hub", [])]
    assert preloaded == [EMBED_MODEL], (
        f"نموذجُ البحث في الكود {EMBED_MODEL} وما يُحمَّل وقتَ البناء {preloaded}")


def test_the_short_description_fits_the_hub_limit():
    assert len(_front_matter()["short_description"]) <= 60


def test_poppler_is_installed_because_the_app_reads_pages_with_pdf2image():
    assert "from pdf2image import" in (ROOT / "app.py").read_text(encoding="utf-8")
    packages = (SPACE / "packages.txt").read_text(encoding="utf-8").split()
    assert packages == ["poppler-utils"], f"حزمُ النظام: {packages}"
