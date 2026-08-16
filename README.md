# Transkriptor Pro — YouTube Transcript and AI Summary Assistant

[English](README.md) | [Türkçe](README_TR.md)

Transkriptor Pro is a Flask application that retrieves YouTube captions, produces short summaries and structured study notes, and detects videos from pasted or uploaded screenshots using multimodal AI and OCR.

## Features

- Transcript retrieval from a YouTube URL or video ID
- Screenshot analysis for video titles and channel names
- Gemini model fallback and retry chain
- Local extractive summarizer when AI is unavailable
- OCR.space fallback for image text extraction
- Persistent SQLite cache
- Responsive light/dark interface
- Timestamp links, clipboard copy, and text download

## Requirements

- Python 3.12+
- Linux, macOS, or Windows (platform-specific launchers are included)

## Setup

```bash
python -m venv venv
pip install -r requirements.txt
```

Create a `.env` file from `.env.example` and add your own credentials:

```env
GEMINI_API_KEY=your_key
OCR_SPACE_KEY=your_optional_key
```

Never commit the `.env` file.

## Run

```bash
python app.py
```

Open `http://127.0.0.1:5000`. Linux users can also use `./run.sh`; Windows launchers are included in the repository.

