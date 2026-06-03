# WizTree CLI Agent — Documentation Index

> **Version**: 1.5.0 | **Last Updated**: 2026-06-04 | **License**: MIT

AI-powered disk cleanup assistant wrapping WizTree CLI with LLM-driven intelligent file analysis and safe human-in-the-loop cleanup.

## Quick Links

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Project architecture, module design, data flow, and directory tree |
| [API_REFERENCE.md](API_REFERENCE.md) | Complete module/class/function reference |
| [CONFIGURATION.md](CONFIGURATION.md) | LLM Router config, Provider catalog, API keys, routing strategies |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Development guide, build, test, changelog |

## Quick Start

```bash
pip install -r requirements.txt
python app.py --cli          # CLI mode (no API key needed)
python cli.py --interactive  # Interactive CLI
python cli.py --scan "C:\Users" --analyze  # Scan + analyze
python app.py                # GUI mode (requires tkinter)
```

## Project Stats

- **Source files**: ~35 Python files, ~7,500+ lines
- **Test files**: ~30 test files, 400+ tests
- **Core modules**: Scanner, Analyzer, Safety, UI, Models, Utils
- **LLM Providers**: 6 (DeepSeek, OpenAI, Anthropic, OpenRouter, SiliconFlow, Ollama)
- **Themes**: 6 dark themes (Steam Dark, Catppuccin Mocha, OLED Black, GitHub Dark, Nord, Dracula)
