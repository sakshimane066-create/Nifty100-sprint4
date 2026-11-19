# Deployment notes

The project spec lists cloud deployment as out of scope (X06): the dashboard is meant to run locally
(`streamlit run src/dashboard/app.py`). If you still want a shareable link, use **Streamlit Community Cloud**.

## Before you publish - confidentiality
The project document is marked CONFIDENTIAL / INTERNAL USE ONLY and the data comes from Bluestock.
Use a **private** GitHub repository, restrict the app's viewers in Streamlit's sharing settings, and get your mentor's
OK first. Never use a public repo.

## Steps
1. Create a private GitHub repo and push the project (`git init`, `git add .`, `git commit`, `git push`).
   `data/nifty100.db` (~2 MB) must be committed - the app reads it directly. `.gitignore` already excludes `.env`.
2. Go to share.streamlit.io -> New app -> pick the repo and branch.
3. **Main file path:** `src/dashboard/app.py`. **Python version:** 3.11. Dependencies come from `requirements.txt`.
4. Deploy. Pages are picked up from `src/dashboard/pages/` automatically.

## Notes
* Logos need outbound internet (website favicons) - Streamlit Cloud has it; otherwise coloured ticker badges are shown.
* Rebuilding data is a local step: run `make all` (or the four `python -m ...` commands), then commit the new `nifty100.db`.
* Free-tier apps sleep after inactivity; the first load afterwards takes ~30 s.
