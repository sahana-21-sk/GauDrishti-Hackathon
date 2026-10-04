"""Run at home with internet: saves backup voice files so audio works even if gTTS fails on stage."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from gtts import gTTS
ROOT = Path(__file__).resolve().parent.parent
import types, importlib
st_stub = types.ModuleType("streamlit"); st_stub.secrets = {}; st_stub.session_state = {}
sys.modules.setdefault("streamlit", st_stub)
import utils as U
for folder in (ROOT / "data" / "live", ROOT / "data" / "demo"):
    p = folder / "results.json"
    if not p.exists(): continue
    for a in json.loads(p.read_text(encoding="utf-8"))["alerts"]:
        for lang in U.LANGS.values():
            txt = U._fallback(a, lang, "today 4 PM to 8 PM").split("\nVet note:")[0]
            try:
                gTTS(text=txt, lang=lang).save(str(ROOT / "data" / "audio" / f"{a['id']}_{lang}.mp3")); print("saved", a["id"], lang)
            except Exception as e:
                print("failed", a["id"], lang, e)
