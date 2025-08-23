# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a Text-to-Speech (TTS) application that uses OpenAI's TTS API to convert text to speech with a Python GUI (Tkinter). The application supports multiple voices, batch processing of text chunks, and audio playback with pause/skip/previous controls.

## Repository Information

- **Repository**: https://github.com/stho32/TTS
- **Language**: Python 3.11+
- **GUI Framework**: Tkinter
- **Audio Backend**: pygame (preferred) with winsound fallback on Windows

## Development Environment

### Prerequisites

1. Python 3.11 or higher
2. OpenAI API key set as environment variable: `OPENAI_API_KEY`
3. uv (Python package manager) - used by start.bat

### Dependencies

The application uses inline script dependencies (PEP 723):
- `openai>=1.40.0` - OpenAI SDK for TTS API
- `pygame>=2.6.0` - Audio playback library

### Running the Application

**Windows (Batch Script)**:
```powershell
./start.bat
```

**Direct Python Execution**:
```bash
uv run python tts_app.py
```

**Alternative without uv**:
```bash
# Install dependencies first
pip install openai pygame

# Run the app
python tts_app.py
```

## Code Architecture

### Main Components

1. **tts_app.py** (Single file application ~770 lines)
   - **TTSWorker**: Background thread handling TTS synthesis and playback
     - Manages audio generation queue
     - Handles playback control (play/pause/stop/skip/previous)
     - Creates temporary WAV files for each text chunk
     - Supports voice randomization per chunk
   
   - **App**: Main Tkinter GUI class
     - Text input area with syntax highlighting for current chunk
     - Control panel for model/voice selection
     - Playback controls (play, pause, stop, skip, previous)
     - Progress bar and status display
     - Log window for debugging
     - WAV export functionality

### Key Features

- **Text Chunking**: Intelligently splits text at paragraph breaks and markdown headings
- **Multi-Voice Support**: 11 OpenAI voices (alloy, echo, fable, onyx, nova, shimmer, coral, verse, ballad, ash, sage)
- **Configurable Chunk Size**: 200-4000 characters per chunk (default: 800)
- **Audio Backends**: Dual backend support (pygame preferred, winsound fallback)
- **Export Capability**: Combine and save generated chunks as single WAV file

### API Integration

Uses OpenAI's TTS API with:
- Default model: `gpt-4o-mini-tts`
- Response format: WAV
- Streaming support with fallback to non-streaming

## Testing and Debugging

### Manual Testing Checklist

1. **Basic Functionality**:
   - Text input and synthesis
   - Voice selection and randomization
   - Playback controls (play/pause/stop/skip/previous)
   - Progress tracking

2. **Edge Cases**:
   - Empty text handling
   - Very long text (multiple chunks)
   - API key validation
   - Network error handling

3. **Platform Testing**:
   - Windows with winsound
   - Cross-platform with pygame

### Common Issues

1. **Missing API Key**: Ensure `OPENAI_API_KEY` environment variable is set
2. **Audio Playback Issues**: Check pygame installation or winsound availability on Windows
3. **Temporary Files**: App creates temp directory `tts_openai_*` - cleaned on exit

## Git Workflow

### Committing Changes
```bash
git add .
git commit -m "Description of changes"
git push origin main
```

### Recent Commits
- Text-to-Speech application with OpenAI integration
- Batch start script for Windows

## Windows-Specific Notes

The application is optimized for Windows but works cross-platform:
- Batch script (`start.bat`) for easy Windows execution
- winsound support as audio backend on Windows
- Platform detection with appropriate warnings for non-Windows systems

## Tech Stack Reference

Based on user preferences:
- Primary development on Windows
- PowerShell for scripting (though this app uses Python)
- No UTF-8 icons in code - keep it simple and direct
