# Shorts Platform

A personal tool that turns a prepared script into a finished faceless YouTube Short (9:16 MP4).

You supply the scenes: one script line and one visual prompt per scene. The platform generates a voiceover and word timings for each scene, finds an image or clip for it, assembles the video, and pauses so you can review and fix it in the browser. After you approve, it renders the final MP4.

Research, splitting the transcript into scenes, and uploading to YouTube stay manual.

## How it works

```
Voiceover -> Timing -> Media -> Assemble -> Review (pause) -> Render -> Download MP4
```

- **Voiceover:** one TTS call per scene. The audio length sets the scene duration.
- **Timing:** Whisper gives word-level timestamps for captions.
- **Media:** stock footage first (Pexels, Pixabay, ranked with CLIP), image generation as a fallback, or your own upload.
- **Review:** an in-browser editor to swap media, edit text and voice, set motion and focal point, then approve.
- **Render:** each scene renders as its own cached segment, then FFmpeg joins them.

The full design is in [docs/spec.html](docs/spec.html).

## Stack

- **Frontend:** React, TypeScript, Vite, Zustand, Remotion Player
- **Backend:** FastAPI, LangGraph (SQLite checkpointer)
- **Data:** SQLite and a local `storage/` folder
- **Local tools:** FFmpeg, faster-whisper

## Requirements

- Node.js
- Python 3.12
- FFmpeg and ffprobe on your PATH (needed from the render phase)
- API keys for a TTS provider, Pexels, Pixabay and an image generation API

## Setup

```
git clone https://github.com/Amank7501/Shorts-Platform.git
cd Shorts-Platform

# backend
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# frontend
cd ..\frontend
npm install
```

Copy `.env.example` to `.env` in the project root and fill in your API keys. Do not commit `.env`.

## Run

Backend, from `backend/`:

```
.venv\Scripts\uvicorn app.main:app --port 8010 --reload
```

Frontend, from `frontend/`:

```
npm run dev
```

Open http://localhost:5173. The frontend proxies `/api` and `/files` to the backend on port 8010.

## Project layout

```
backend/    FastAPI app
frontend/   React app
renderer/   Remotion scene composition and segment renderer (Node)
storage/    local files and the SQLite database (git-ignored)
docs/       build spec
```

## Status

Under active development. The project scaffold is done; the video JSON schema, render pipeline and editor are still to come. See the build phases in the spec.
