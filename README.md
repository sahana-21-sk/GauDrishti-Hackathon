# Gaudrishti: Giving the silent herd a voice
Non-invasive cattle health monitoring from ordinary CCTV video. A screening aid, not a diagnosis: a vet confirms.

## The rule
**The UI adapts to the pipeline. The pipeline does not adapt to the UI.**
Frozen (never edit): `colab/analysis.py`, `colab/process_video.py`, `colab/verify_output.py`, `SCHEMA.md`, `data/live/`.
Prove it any time: `python tests/check_frozen.py`. Editable: `app/app.py`, `app/utils.py`.

## Run the dashboard
```
pip install -r requirements.txt
streamlit run app/app.py
```
It opens on the verified live result in `data/live/` (2 cows, 1 watchlist, 0 alerts, Cow #2 about 0.39).
Pick **Demo herd** in the sidebar for the synthetic herd (the offline fallback).

## Pages
Overview · Alerts & Watchlist · Cow Health Cards · Herd Map · CCTV & Evidence · Analyze a Video · About & Method.
English / Hindi / Telugu explanations (Gemini, with template fallback) and voice (gTTS).

## Analyze your own video
- **On a laptop:** `pip install -r requirements-local.txt`, then use *Analyze a Video* (runs the frozen pipeline).
- **Anywhere:** process in Colab (`colab/gaudrishti_colab.ipynb`), then use *Load Colab results* with `output.zip`, or unzip it into `data/live/`.

## Gemini (optional)
Copy `.env.example` to `.env` and add `GEMINI_API_KEY`. On Streamlit Cloud: App settings > Secrets. Never commit the key.

## Deploy
Push to GitHub > share.streamlit.io > main file `app/app.py`. `data/live/` is committed on purpose so the deployed app shows the real result.
The free host cannot run YOLO, so video processing is off there; Colab results and Demo Mode work.

## Tests
`python tests/check_frozen.py` · `python tests/test_app_logic.py` · `python tests/test_pipeline.py`
