# Team plan (2 people, 12 hours)
**Person A = CV (folder `colab/`, `data/live/`)**  |  **Person B = App (folders `app/`, `scripts/`, `data/demo/`, `data/audio/`)**
Nobody edits the other person's folder, so Git merges never conflict. The only shared thing is SCHEMA.md.

| Hour | Person A (CV) | Person B (App) |
|---|---|---|
| 0-1 | TOGETHER: read rules, create GitHub repo, push this project, confirm SCHEMA.md | same |
| 1-2 | Pick the demo video (1-3 min, clear cows, ideally one mounting). Open Colab notebook, run on it | Run the app on Demo Mode (works already). Get Gemini key, put in .env |
| 2-5 | STEP 1+2: run pipeline, verify_output, fix --conf / --feed-zone / thresholds | Polish UI, test Hindi/Telugu text, check each tab |
| 5-6 | INTEGRATION: push output to `data/live/` (unzip output.zip there) | `git pull`, app now shows real results. Report any bug to A |
| 6-8 | Tune thresholds in analysis.py CFG until alerts match what you see in the video | Gemini explanations, voice, pregenerate_audio.py, Health Card polish |
| 8-9 | Re-run final, save final output, record screen of processed video as backup | Deploy on Streamlit Cloud, add GEMINI_API_KEY in Secrets, test on phone |
| 9-10 | TOGETHER: full dry run, fix issues, test Demo Mode by ticking "Force Demo Mode" | same |
| 10-11 | Record demo video (A drives the app, B talks) | Update PPT: only keep what works |
| 11-12 | Submit EARLY. Check all links open | same |

**Git rules (30 seconds):** `git pull --rebase` before every push. Commit small, often. Only touch your own folders.
```
git add . && git commit -m "what I did" && git pull --rebase && git push
```
**If A is late:** B keeps going on Demo Mode and the demo still works. **If B is late:** A can deploy the app as-is.
