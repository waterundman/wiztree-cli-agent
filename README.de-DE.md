# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-400%2B-brightgreen.svg)](tests/)

<p align="center">
  <a href="README.md">🇬🇧 English</a> &nbsp;|&nbsp;
  <a href="README.zh-CN.md">🇨🇳 中文</a> &nbsp;|&nbsp;
  <a href="README.fr-FR.md">🇫🇷 Français</a> &nbsp;|&nbsp;
  <b><a href="README.de-DE.md">🇩🇪 Deutsch</a></b> &nbsp;|&nbsp;
  <a href="README.ja-JP.md">🇯🇵 日本語</a> &nbsp;|&nbsp;
  <a href="README.ru-RU.md">🇷🇺 Русский</a>
</p>

**KI-gestützter Datenträgerbereinigungsassistent** — Kapselt das WizTree-CLI-Tool ein und nutzt LLM-Analyse (Large Language Models) für eine sichere, interaktive Dateibereinigung mit menschlicher Kontrolle.

> **Aktuelle Version: v1.5.0** — Dynamisches LLM-Routing (LatencyProbe + WeightedRouter), CLI-Scripting (Exit-Codes, JSON/CSV-Export), Batch-Scan, virtuelles Scrollen, Scan-Cache, 6 dunkle Designs, Tastenkürzel, Drag & Drop, Prüfprotokoll mit Wiederherstellung, Diff-Vorschau, Squarified-Treemap

---

## Inhaltsverzeichnis

- [Projektübersicht](#projektübersicht)
- [Hauptfunktionen](#hauptfunktionen)
  - [Kernfunktionen (v1.0.0)](#kernfunktionen-v100)
  - [v1.1.0 — UI-Modernisierung](#v110--ui-modernisierung)
  - [v1.2.0 — Sicherheit, Designs & Interaktion](#v120--sicherheit-designs--interaktion)
  - [v1.3.0 — Benutzererfahrung](#v130--benutzererfahrung)
  - [v1.4.0 — Leistung](#v140--leistung)
  - [v1.5.0 — Dynamisches Routing & CLI-Scripting](#v150--dynamisches-routing--cli-scripting)
- [Screenshots](#screenshots)
- [Schnellstart](#schnellstart)
  - [Installation](#installation)
  - [Ausführung](#ausführung)
- [Architektur](#architektur)
  - [Modulübersicht](#modulübersicht)
  - [Datenfluss](#datenfluss)
- [LLM Router](#llm-router)
  - [Unterstützte Anbieter](#unterstützte-anbieter)
  - [Routing-Strategien](#routing-strategien)
  - [Erweiterte Funktionen (v1.5.0)](#erweiterte-funktionen-v150)
  - [Beispiel](#beispiel)
- [Regel-Engine](#regel-engine)
- [Sicherheitsmechanismen](#sicherheitsmechanismen)
- [Konfiguration](#konfiguration)
  - [API-Schlüssel](#api-schlüssel)
  - [WizTree-Pfad](#wiztree-pfad)
  - [Dreistufige Kaskadenkonfiguration](#dreistufige-kaskadenkonfiguration)
- [GUI-Bedienung](#gui-bedienung)
  - [Tastenkürzel (v1.2.0)](#tastenkürzel-v120)
  - [Drag & Drop (v1.2.0)](#drag--drop-v120)
  - [Designs (v1.2.0)](#designs-v120)
- [CLI-Bedienung](#cli-bedienung)
  - [Befehle](#befehle)
  - [Exit-Codes (v1.5.0)](#exit-codes-v150)
  - [Stapelverarbeitung (v1.5.0)](#stapelverarbeitung-v150)
  - [Exportformate (v1.5.0)](#exportformate-v150)
- [Tests](#tests)
- [Projektstruktur](#projektstruktur)
- [Technologie-Stack](#technologie-stack)
- [Häufig gestellte Fragen](#häufig-gestellte-fragen)
- [Lizenz](#lizenz)
- [Mitwirken](#mitwirken)

---

## Projektübersicht

**WizTree CLI Agent** ist ein intelligenter Datenträgerbereinigungsassistent, der die extrem schnelle MFT-Scan-Technologie von WizTree CLI mit der Analysefähigkeit großer Sprachmodelle (LLMs) kombiniert. Das System bietet einen **LLM Router** mit Unterstützung für 6 Anbieter, 4 Routing-Strategien und dynamischer Gewichtung. Steht kein API-Schlüssel zur Verfügung, greift die integrierte **Regel-Engine** mit 10 vordefinierten Bereinigungsregeln als nahtloser Fallback-Mechanismus.

Das Projekt folgt einer strengen **Dreiklang-Architektur**: Scanner → Analyzer → Safety. Jede Zerstörungsoperation durchläuft eine mehrschichtige Sicherheitsprüfung (38 geschützte Systempfade, SQLite-Prüfprotokoll, Dateivalidierung, manueller Bestätigungsdialog) und verwendet `send2trash` für die Verschiebung in den Papierkorb.

---

## Hauptfunktionen

### Kernfunktionen (v1.0.0)

- **WizTree-CLI-Integration**: Hochgeschwindigkeits-Datenträgerscan mittels MFT-Direktauslesung (Master File Table); CSV-Ausgabe wird mit einem Streaming-Parser eingelesen
- **KI-gestützte Analyse**: Nutzt LLMs zur intelligenten Bewertung von Scan-Ergebnissen; identifiziert sicher löschbare Dateien mit Risikobewertung
- **LLM Router**: Einheitliche API-Gateway-Schicht mit Multi-Provider-Routing, Fehlerübergabe (Failover) und Kostenoptimierung; 6 Anbieter, 4 Strategien
- **Regel-Engine**: 10 vordefinierte Bereinigungsregeln (Temporäre Dateien, Cache, Logs, Installationspakete, Downloads, u. a.) als LLM-Fallback — kein API-Schlüssel erforderlich
- **Human-in-the-Loop**: Jeder Löschvorgang erfordert manuelle Prüfung und Bestätigung durch den Benutzer
- **Streaming-JSON-Parser**: Echtzeit-Anzeige der KI-Analyseergebnisse während der Verarbeitung
- **Risikobewertung**: Jede zur Löschung vorgeschlagene Datei erhält eine Risikostufe (LOW / MEDIUM / HIGH / CRITICAL)
- **Papierkorb-Unterstützung**: Verwendet `send2trash` für sichere Löschung über den Papierkorb (Soft Delete)
- **Treemap-Visualisierung**: Grafische Darstellung der Dateigrößenverteilung mittels Squarified-Treemap-Algorithmus
- **Sicherheitsmechanismen**: Pfad-Blacklist (38 geschützte Systempfade), SQLite-Prüfprotokoll, Dateivalidierung, Bestätigungsdialog
- **Zweisprachige Oberfläche**: Deutsch und Englisch

### v1.1.0 — UI-Modernisierung

- **Modernes Designsystem**: Umschaltung zwischen hellem und dunklem Design; professionelle UI-Gestaltung mit `customtkinter`
- **Smooth-Progress-Bar**: 60-fps-Animation für flüssige Fortschrittsanzeige
- **Ladeindikator mit Spinner**: Visuelle Rückmeldung während Scan- und Analysevorgängen
- **Responsives Layout**: Automatische Anpassung an Fenstergrößenänderungen
- **Statistik-Karten**: Echtzeit-Anzeige von Dateianzahl, Gesamtgröße und Scan-Dauer

### v1.2.0 — Sicherheit, Designs & Interaktion

- **Verschlüsselte Schlüsselspeicherung**: API-Schlüssel werden über `keyring` gespeichert (Windows DPAPI / macOS Keychain / Linux Secret Service)
- **6 dunkle Designs**: Steam Dark, Catppuccin Mocha, OLED Black, GitHub Dark, Nord, Dracula — dynamische Umschaltung zur Laufzeit
- **5 Tastenkürzel**: Ctrl+S (Scan), Ctrl+R (Tab aktualisieren), Ctrl+L (Ergebnisse löschen), Ctrl+, (Einstellungen), Esc (Abbrechen)
- **Drag & Drop**: Ordner oder Dateien per Ziehen & Ablegen auf das Hauptfenster legen (via `tkinterdnd2`)
- **Prüfprotokoll & Wiederherstellung**: Jede zerstörerische Aktion wird in SQLite protokolliert; `file_delete`- und `file_move`-Operationen können über den Verlaufs-Tab rückgängig gemacht werden
- **Diff-Vorschau**: Vor jeder Löschung werden Dateigröße, Änderungsdatum und eine deutlich sichtbare Warnung („⚠️ LÖSCHEN“) angezeigt
- **Squarified-Treemap**: Reine-Python-Implementierung nach Bruls et al. (2000), Algorithmus 4 — keine Drittanbieter-Bibliothek erforderlich
- **3-stufige Kaskadenkonfiguration**: Eingebaute Standardwerte → `~/.wiztree-cli-agent/config.json` → Laufzeit-Überschreibungen
- **LLM-Models- und Prompts-Tabs**: Modelkatalog durchsuchen und Prompts bearbeiten, ohne die GUI zu verlassen
- **Statusleiste**: Scan-Statistiken und Betriebszustand (Scan wird ausgeführt / Analyse läuft / Bereit / Fehler)

### v1.3.0 — Benutzererfahrung

- **Skeleton-Screen**: Platzhalter-UI während des Ladens; verbessert die Wahrnehmung der Leistung
- **Theme-Wechsel-Callbacks**: Saubere Integration von Designwechseln in `ttk.Style`
- **Verbesserte Fehlerbehandlung**: Strukturierte Fehleranzeige in der Statusleiste

### v1.4.0 — Leistung

- **Virtuelles Scrollen**: `VirtualTreeview`-Komponente rendert nur sichtbare Zeilen; Bewältigt problemlos +100.000 Dateien
- **Speicheroptimierung**: `FileInfo` verwendet `__slots__`; reduziert den Speicherverbrauch pro Datei um ~60 %
- **Scan-Cache**: 1-stündige TTL (Time-To-Live); vermeidet wiederholte Scans desselben Laufwerks
- **Streaming-CSV-Parser**: Zeilenweise Verarbeitung der WizTree-CSV-Ausgabe; kein vollständiges Einlesen in den Speicher erforderlich
- **Leistungskennzahlen**: Scan von 500.000 Dateien in < 5 Sekunden, Speicherverbrauch < 200 MB

### v1.5.0 — Dynamisches Routing & CLI-Scripting

- **LatencyProbe**: Hintergrund-Thread pingt regelmäßig alle verfügbaren Provider; misst die Latenz in Echtzeit
- **WeightedRouter**: Dynamische Gewichtung der Provider basierend auf Latenz, Erfolgsrate und Kosten; optimale Auswahl für jede Anfrage
- **batch_chat**: Parallele Batch-Anfragen an mehrere Provider; reduziert die Gesamtwartezeit bei Massenverarbeitung
- **RequestCoalescer**: Automatische Zusammenführung identischer gleichzeitiger Anfragen; vermeidet doppelte API-Aufrufe
- **CLI-Scripting**: Exit-Codes (0 = Erfolg, 1 = Fehler, 2 = ungültige Argumente), `--quiet` (stille Ausgabe), `--json` (strukturierte JSON-Ausgabe), `--no-color` (Farben deaktivieren)
- **OutputFormatter**: Formatierte Ausgabe mit einstellbarem Stil (text/json/csv)
- **Stapelverarbeitung**: `--batch` und `--batch-file` für die Verarbeitung mehrerer Pfade in einem Durchlauf
- **JSON/CSV-Export**: Export der Scan- und Analyseergebnisse in JSON- oder CSV-Format
- **Integrationstests**: +30 neue Tests (5 Szenarien über alle 6 Stufen); Gesamttestzahl: 400+

---

## Screenshots

![WizTree CLI Agent](docs/screenshot.png)

> *Hinweis: Fügen Sie einen Screenshot unter `docs/screenshot.png` ein, um die GUI visuell darzustellen.*

---

## Schnellstart

### Installation

**Voraussetzungen**: Python 3.10 oder höher, WizTree CLI (kostenlos erhältlich unter [https://diskanalyzer.com](https://diskanalyzer.com))

```bash
# Repository klonen
git clone https://github.com/wiztree-cli-agent.git
cd wiztree-cli-agent

# Abhängigkeiten installieren
pip install -r requirements.txt
```

### Ausführung

```bash
# CLI-Modus (kein API-Schlüssel erforderlich — verwendet Regel-Engine)
python app.py --cli

# Interaktiver CLI-Modus
python cli.py --interactive

# Scannen und analysieren
python cli.py --scan "C:\Users" --analyze

# Scannen mit JSON-Ausgabe (v1.5.0)
python cli.py --scan "D:\" --analyze --json --quiet

# Stapelverarbeitung mehrerer Pfade (v1.5.0)
python cli.py --batch --batch-file pfade.txt --analyze

# Export nach JSON/CSV (v1.5.0)
python cli.py --scan "C:\Users" --analyze --export results.json

# GUI-Modus (erfordert tkinter)
python app.py

# Oder per Startskript:
run_gui.bat
```

---

## Architektur

Das System folgt einer streng modularen **Dreiklang-Architektur** mit drei Hauptmodulen: **Scanner** → **Analyzer** → **Safety**. Jedes Modul ist über klar definierte Schnittstellen (abstrakte Basisklassen) entkoppelt und kann unabhängig getestet werden.

```
┌──────────────────────────────────────────────────────────────────┐
│                     WizTree CLI Agent                             │
│                                                                   │
│    ┌──────────┐      ┌──────────┐        ┌──────────┐           │
│    │ Scanner  │─────▶│ Analyzer │───────▶│  Safety  │           │
│    │          │      │          │        │          │           │
│    └────┬─────┘      └────┬─────┘        └────┬─────┘           │
│         │                 │                    │                  │
│         ▼          ┌──────┴──────┐             ▼                  │
│    ┌─────────┐    ▼             ▼        ┌──────────┐           │
│    │WizTree  │  ┌──────────┐ ┌────────┐  │ Blocklist │           │
│    │  CLI    │  │ LLMRouter│ │Rule    │  │ (38 Pfade)│           │
│    │(MFT-Scan)│  │ 6 Anbieter│ │Engine  │  │ AuditLog   │           │
│    └─────────┘  │ 4 Strategien│10 Regeln│  │ (SQLite)  │           │
│                 │ Weighted  │ │        │  │ FileValid  │           │
│                 │ Router    │ │        │  │ ConfirmDlg │           │
│                 └──────────┘ └────────┘  └──────────┘           │
└──────────────────────────────────────────────────────────────────┘
```

### Modulübersicht

| Modul | Beschreibung | Schlüsselklassen |
|-------|-------------|------------------|
| **Scanner** | Kapselt WizTree CLI für Hochgeschwindigkeits-Datenträgerscans; unterstützt MFT-Scan, Tiefensuche und Pfadvalidierung | `WizTreeScanner`, `PathValidator`, `DeepSearcher`, `ScanProgress` |
| **Analyzer** | Führt LLM-basierte oder regelbasierte Dateianalyse durch; enthält den LLM Router mit 6 Anbietern und die Regel-Engine mit 10 Regeln | `LLMAnalyzer`, `LLMRouter`, `StreamingJsonParser`, `RuleEngine` |
| **Safety** | Mehrschichtiger Sicherheitsmechanismus: Pfad-Blacklist (38 Einträge), Dateivalidierung, SQLite-Prüfprotokoll, manueller Bestätigungsdialog | `ComprehensiveSafetyManager`, `Blocklist`, `AuditLogger`, `ConfirmDialog` |
| **UI** | Grafische Benutzeroberfläche basierend auf `customtkinter`; 6 Themen, Treemap, virtuelles Scrollen, Tastenkürzel, Drag & Drop | `MainWindow`, `ConfigPanel`, `FileTable`, `TreemapView`, `ModernTheme` |
| **Models** | Datenmodelle mit `__slots__`-Optimierung für geringen Speicherverbrauch | `FileInfo`, `ScanResult`, `AnalysisResult`, `RiskLevel` |
| **Utils** | Hilfsfunktionen: 3-stufige Kaskadenkonfiguration, verschlüsselte Schlüsselspeicherung über `keyring` | `ConfigLoader`, `CredentialStore` |

### Datenfluss

```
Benutzereingabe (CLI/GUI)
    │
    ▼
Scanner ──▶ WizTree CLI ──▶ CSV-Ausgabe ──▶ FileInfo[]
    │
    ▼
Analyzer ──▶ LLM Router (falls API-Schlüssel vorhanden)
    │            ├── LatencyProbe (Latenzmessung)
    │            ├── WeightedRouter (dynamische Gewichtung)
    │            ├── Circuit Breaker (CLOSED → OPEN → HALF_OPEN)
    │            └── RequestCoalescer (Anfragenzusammenführung)
    │         ODER Regel-Engine (Fallback, kein API-Schlüssel nötig)
    │
    ▼
Safety ──▶ Blacklist-Prüfung ──▶ Dateivalidierung ──▶ Prüfprotokoll
    │                                                       │
    ▼                                                       ▼
Benutzerbestätigung ──▶ send2trash (Papierkorb) ──▶ Prüfeintrag (SQLite)
```

---

## LLM Router

Der **LLM Router** ist die zentrale API-Gateway-Schicht des Systems. Er verwaltet 6 LLM-Anbieter, unterstützt 4 Routing-Strategien und bietet erweiterte Funktionen wie Latenzmessung, dynamische Gewichtung und Anfragenzusammenführung.

### Unterstützte Anbieter

| Anbieter | Umgebungsvariable | Kostenloses Modell | Besonderheit |
|----------|------------------|-------------------|--------------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `deepseek-v4-flash` | Direkte Anbindung aus China, hohes Preis-Leistungs-Verhältnis |
| **OpenAI** | `OPENAI_API_KEY` | — | GPT-4o-mini, breite Modellpalette |
| **Anthropic** | `ANTHROPIC_API_KEY` | — | Claude-3-haiku, Claude-3.5-sonnet |
| **OpenRouter** | `OPENROUTER_API_KEY` | `google/gemini-2.0-flash-exp:free` | Aggregiert 315+ Modelle, einheitlicher API-Zugang |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | `deepseek-ai/DeepSeek-V3`, `Qwen/Qwen2.5-7B-Instruct` | Kostenlose Modelle aus China, GPU-Cloud |
| **Ollama** | Kein Schlüssel nötig | `llama3.2`, `qwen2.5` | Lokale Ausführung, keine Internetverbindung erforderlich, völlig kostenlos |

### Routing-Strategien

| Strategie | Beschreibung | Anwendungsfall |
|-----------|-------------|----------------|
| `cost` | **Kostenpriorität** — wählt den günstigsten Anbieter aus | Budgetbeschränkungen, Massenverarbeitung |
| `latency` | **Geschwindigkeitspriorität** — wählt den Anbieter mit der geringsten Latenz | Interaktive Sitzungen, Echtzeitanforderungen |
| `fallback` | **Fehlerübergabe** — versucht Anbieter nacheinander; automatische Umschaltung bei Fehlern | Hohe Zuverlässigkeit, Produktionsumgebungen |
| `manual` | **Manuelle Auswahl** — Benutzer gibt Anbieter und Modell explizit vor | Debugging, Tests, spezifische Modellanforderungen |

### Erweiterte Funktionen (v1.5.0)

| Funktion | Beschreibung |
|----------|-------------|
| **LatencyProbe** | Hintergrund-Thread pingt regelmäßig alle verfügbaren Provider (alle 60 Sekunden); zeichnet Latenz, Erfolgsrate und Fehlerquoten auf |
| **WeightedRouter** | Berechnet dynamische Gewichtungen basierend auf Latenz (30 %), Erfolgsrate (40 %) und Kosten (30 %); wählt den optimalen Provider für jede Anfrage |
| **Circuit Breaker** | Unterbricht nach 3 aufeinanderfolgenden Fehlern automatisch die Verbindung zu einem Provider; versucht nach 60 Sekunden erneut (HALF_OPEN → CLOSED oder OPEN) |
| **RequestCoalescer** | Fasst identische gleichzeitige Anfragen zusammen; die erste Anfrage wird ausgeführt, nachfolgende erhalten das gleiche Ergebnis — vermeidet doppelte API-Kosten |
| **batch_chat** | Parallele Verarbeitung mehrerer Anfragen über `ThreadPoolExecutor`; konfigurierbare maximale Parallelität |

### Beispiel

```python
from src.analyzer import LLMRouter, RoutingStrategy

# Router mit Fehlerübergabe-Strategie erstellen
router = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# Gewichtete Strategie mit Latenzmessung
router.set_strategy(RoutingStrategy.LATENCY)

# Chat-Anfrage senden
response = router.chat(
    messages=[{"role": "user", "content": "Analysiere diese Dateien: ..."}],
    model="deepseek-v4-flash"
)

# Batch-Anfragen (v1.5.0)
results = router.batch_chat(
    messages_list=[
        [{"role": "user", "content": "Frage 1"}],
        [{"role": "user", "content": "Frage 2"}],
    ]
)
```

---

## Regel-Engine

Die **Regel-Engine** dient als Fallback-Mechanismus, wenn kein LLM-API-Schlüssel konfiguriert ist. Sie enthält 10 vordefinierte Bereinigungsregeln, die Dateien anhand von Dateinamensmustern, Pfaden und Größen Schwellenwerten analysieren.

| Regel | Muster | Risiko | Größenbeschränkung |
|-------|--------|--------|-------------------|
| Temporäre Dateien | `\.(tmp\|temp\|bak\|old\|log\|cache)$` | LOW | > 1 MB |
| Installationspakete | `\.(msi\|exe\|setup\|install)$` | MEDIUM | > 10 MB |
| Download-Ordner | `\\Downloads\\` im Pfad | MEDIUM | > 50 MB |
| Cache-Dateien | `\\cache\\`, `\\Cache\\`, `AppData\Local\*.Cache` | LOW | > 5 MB |
| Log-Dateien | `\.log$` | LOW | > 1 MB |
| Papierkorb | `\\$Recycle.Bin\\`, `\.Trash` | LOW | Keine |
| Thumbs.db | `thumbs\.db$` | LOW | Keine |
| Desktop.ini | `desktop\.ini$` | LOW | Keine |
| Dump-Dateien | `\.dmp$`, `\.minidump$`, `\.mdmp$`, `\.hdmp$` | MEDIUM | > 10 MB |
| Alte Installationen | `Windows\.old`, `$Windows.~BT`, `$Windows.~WS` | HIGH | > 100 MB |

---

## Sicherheitsmechanismen

Das **Safety-Modul** implementiert eine mehrschichtige Sicherheitsarchitektur:

| Schicht | Beschreibung | Details |
|---------|-------------|---------|
| **1. Pfad-Blacklist** | 38 geschützte Systempfade | Windows-Systemverzeichnisse (`C:\Windows`, `C:\Program Files`), Benutzerprofile, Boot-Dateien |
| **2. Dateivalidierung** | Prüfung vor jeder Operation | Dateiexistenz, Zugriffsrechte, Sperrstatus, Pfadauflösung |
| **3. Prüfprotokoll** | SQLite-basierte Aufzeichnung | Jede `file_delete`-, `file_move`- oder `file_trash`-Operation wird mit Zeitstempel, Benutzer und Ergebnissen protokolliert |
| **4. Bestätigungsdialog** | Manuelle Prüfung | Dateidetails (Größe, Pfad, Änderungsdatum) und Risikostufe werden vor der Bestätigung angezeigt |
| **5. Diff-Vorschau** | Vorher-Nachher-Ansicht | Zeigt zu löschende Dateien mit Warnsymbol („🗑️ LÖSCHEN") und Metadaten |
| **6. Papierkorb** | Soft Delete via `send2trash` | Dateien werden in den Papierkorb verschoben, nicht endgültig gelöscht |
| **7. Wiederherstellung** | AuditLogger.restore() | Gelöschte oder verschobene Dateien können über den Verlaufs-Tab wiederhergestellt werden |

---

## Konfiguration

### API-Schlüssel

API-Schlüssel werden über die verschlüsselte `keyring`-Speicherung verwaltet (v1.2.0) und optional über Umgebungsvariablen gesetzt:

```bash
# DeepSeek (empfohlen — kostenloses Modell verfügbar)
set DEEPSEEK_API_KEY=sk-ihr-schlüssel

# OpenAI
set OPENAI_API_KEY=sk-ihr-schlüssel

# Anthropic
set ANTHROPIC_API_KEY=sk-ant-ihr-schlüssel

# OpenRouter (kostenloses Gemini-Modell)
set OPENROUTER_API_KEY=sk-ihr-schlüssel

# SiliconFlow (kostenlose Modelle)
set SILICONFLOW_API_KEY=sk-ihr-schlüssel
```

### WizTree-Pfad

Standardmäßig sucht das Tool nach `WizTree64.exe` unter `W:\WizTree\WizTree64.exe`. Sie können den Pfad in der GUI oder Konfigurationsdatei anpassen. WizTree CLI ist kostenlos erhältlich unter [https://diskanalyzer.com](https://diskanalyzer.com).

### Dreistufige Kaskadenkonfiguration

Die Konfiguration folgt einem 3-stufigen Kaskadensystem (v1.2.0):

| Stufe | Quelle | Beschreibung |
|-------|--------|-------------|
| 1 | `config/llm_config.json` | Integrierte Standardkonfiguration (Provider, Modelle, Strategien) |
| 2 | `~/.wiztree-cli-agent/config.json` | Benutzerspezifische Überschreibungen (wird bei erster Ausführung automatisch erstellt) |
| 3 | Laufzeit-Überschreibungen | Programmgesteuerte Änderungen während der Sitzung (z. B. über die GUI) |

Bei der ersten Ausführung werden die Einstellungen von `config/llm_config.json` automatisch nach `~/.wiztree-cli-agent/config.json` migriert.

---

## GUI-Bedienung

### Tastenkürzel (v1.2.0)

| Kürzel | Aktion | Beschreibung |
|--------|--------|-------------|
| `Ctrl+S` | 🔍 Scan starten | Startet den Datenträgerscan (entspricht Klick auf „Scan & Analyze") |
| `Ctrl+R` | 🔄 Tab aktualisieren | Aktualisiert den aktuellen Tab (Verlauf/Modelle/Prompts) |
| `Ctrl+L` | 🧹 Ergebnisse löschen | Leert alle Ergebnis-Tabellen und den gecachten Scan |
| `Ctrl+,` | ⚙️ Einstellungen | Öffnet den Einstellungsdialog |
| `Esc` | ❌ Abbrechen | Bricht den aktuellen Vorgang ab |

> Tastenkürzel degradieren elegant: Fehlt die zugehörige Methode im Fenster, wird das Kürzel übersprungen — andere Kürzel bleiben funktionsfähig.

### Drag & Drop (v1.2.0)

Ziehen Sie Ordner oder Dateien per Drag & Drop auf das Hauptfenster:

- **Einzelner Ordner** → Wird in das Feld „Tiefensuche-Ordner" eingetragen
- **Einzelne Datei** → Das übergeordnete Verzeichnis wird eingetragen
- **Mehrere Pfade** → Der gemeinsame übergeordnete Pfad wird ermittelt und eingetragen

Drag & Drop wird über `tkinterdnd2` realisiert (bei Nichtverfügbarkeit automatische Deaktivierung — alle anderen Funktionen arbeiten normal weiter).

### Designs (v1.2.0)

Das System bietet 6 dunkle Designs, die zur Laufzeit dynamisch umgeschaltet werden können:

| Design | Beschreibung |
|--------|-------------|
| **Steam Dark** | Abgeleitet vom Dunkeldesign des Steam-Clients; gedämpfte Blau-Grau-Töne |
| **Catppuccin Mocha** | Warme, samtige Farbpalette; beliebt in der Entwickler-Community |
| **OLED Black** | Reines Schwarz (#000000); optimiert für OLED-Bildschirme, reduziert Stromverbrauch |
| **GitHub Dark** | Angelehnt an GitHub-Dunkeldesign; vertraute blau-graue Ästhetik |
| **Nord** | Arktisch-bläuliches Design; hoher Kontrast, augenschonend |
| **Dracula** | Berühmtes dunkelviolettes Design; kräftige Akzentfarben |

---

## CLI-Bedienung

### Befehle

```bash
# Vollständige CLI-Hilfe anzeigen
python cli.py --help

# Interaktiver Modus
python cli.py --interactive

# Scan + Analyse
python cli.py --scan "C:\Users\Benutzername" --analyze

# Nur scan (ohne Analyse)
python cli.py --scan "D:\Dokumente"

# Tiefensuche in einem Ordner
python cli.py --deep-search "C:\Users\Benutzername\Downloads"
```

### Exit-Codes (v1.5.0)

| Code | Bedeutung | Beschreibung |
|------|-----------|-------------|
| `0` | Erfolg | Vorgang erfolgreich abgeschlossen |
| `1` | Allgemeiner Fehler | Laufzeitfehler, Ausnahmefehler |
| `2` | Ungültige Argumente | Falsche oder fehlende Befehlszeilenargumente |

### Stapelverarbeitung (v1.5.0)

```bash
# Stapeldatei (eine Pfad pro Zeile)
python cli.py --batch --batch-file pfade.txt --analyze

# Stapelverarbeitung mit JSON-Export
python cli.py --batch --batch-file pfade.txt --analyze --export ergebnisse.json
```

### Exportformate (v1.5.0)

```bash
# JSON-Ausgabe
python cli.py --scan "C:\Users" --analyze --json

# CSV-Ausgabe
python cli.py --scan "C:\Users" --analyze --csv

# In Datei exportieren
python cli.py --scan "C:\Users" --analyze --export ergebnisse.json

# Stille Ausgabe (keine Konsolenausgabe)
python cli.py --scan "C:\Users" --analyze --quiet --json --export ergebnisse.json
```

---

## Tests

Das Projekt enthält eine umfangreiche Test Suite mit über 400 Tests.

### Testausführung

```bash
# Alle Tests ausführen
pytest tests/ -v

# Bestimmte Testmodule
pytest tests/test_scanner.py -v
pytest tests/test_analyzer.py -v
pytest tests/test_safety.py -v
pytest tests/test_router.py -v

# Mit Codeabdeckung
pytest tests/ --cov=src/ --cov-report=term-missing

# LLM Router-Demo
python tests/demo_router.py
```

### Testabdeckung

| Kategorie | Anzahl | Beschreibung |
|-----------|--------|-------------|
| **Komponententests** | 72+ | Scanner, Analyzer, Safety, Datenmodelle |
| **Integrationstests** (v1.5.0) | 30+ | 5 Szenarien über alle 6 Stufen |
| **UI-Tests** (v1.1.0) | 15+ | MainWindow, FileTable, ResultsView, ProgressBar |
| **Gesamt** | **400+** | Alle Tests bestanden, keine Regressionen |

---

## Projektstruktur

```
wiztree-cli-agent/
├── app.py                          # GUI-Anwendungseinstieg (140 Zeilen)
├── cli.py                          # CLI-Einstieg (403 Zeilen, interaktiv/stapel/scriptable)
├── build.py                        # PyInstaller-Buildskript (210 Zeilen)
├── audit.db                        # SQLite-Prüfprotokoll (Laufzeit)
├── requirements.txt                # Python-Abhängigkeiten
├── WizTreeCLIAgent.spec            # PyInstaller-Spezifikation
├── run_cli.bat                     # CLI-Starter
├── run_gui.bat                     # GUI-Starter
│
├── config/
│   └── llm_config.json             # LLM-Router-Konfiguration (Anbieter, Modelle)
│
├── docs/                           # Dokumentation
│   ├── ARCHITECTURE.md             # Architekturdesign, Datenfluss
│   ├── API_REFERENCE.md            # Vollständiges API-Referenzhandbuch
│   ├── CONFIGURATION.md            # Konfigurationsleitfaden
│   ├── DEVELOPMENT.md              # Entwicklerleitfaden, Build, Test
│   └── INDEX.md                    # Dokumentationsindex
│
├── src/                            # Quellcode
│   ├── __init__.py                 # Paketdefinition, __version__ = "1.5.0"
│   ├── scanner/                    # Scanner-Modul (6 Dateien)
│   │   ├── interface.py            # ScannerInterface (abstrakte Basisklasse)
│   │   ├── wiztree_scanner.py      # WizTreeScanner (MFT-Scan, CSV-Parse, Cache)
│   │   ├── path_validator.py       # PathValidator (Existenz, Rechte, Systempfade)
│   │   ├── scan_progress.py        # ScanProgress (Fortschritt, Abbruch)
│   │   ├── deep_search.py          # DeepSearcher (rekursive Suche, Muster)
│   │   └── options.py              # ScanOptions (Tiefe, Größe, Ausschlüsse)
│   │
│   ├── analyzer/                   # Analyzer-Modul (7 Dateien)
│   │   ├── interface.py            # AnalyzerInterface (abstrakte Basisklasse)
│   │   ├── llm_analyzer.py         # LLMAnalyzer (596 Zeilen, Lazy Init)
│   │   ├── llm_router.py           # LLMRouter (1241 Zeilen, v1.5.0)
│   │   ├── json_parser.py          # StreamingJsonParser (253 Zeilen)
│   │   ├── rule_engine.py          # RuleEngine (279 Zeilen, 10 Regeln)
│   │   ├── model_catalog.py        # ModelCatalog (396 Zeilen)
│   │   └── prompt_store.py         # PromptStore (244 Zeilen)
│   │
│   ├── safety/                     # Safety-Modul (6 Dateien)
│   │   ├── interface.py            # SafetyInterface (245 Zeilen)
│   │   ├── blocklist.py            # Blocklist (226 Zeilen, 38 Pfade)
│   │   ├── audit_logger.py         # AuditLogger (804 Zeilen, SQLite, Wiederherstellung)
│   │   ├── file_validator.py       # FileValidator (328 Zeilen)
│   │   ├── confirm_dialog.py       # ConfirmDialog (379 Zeilen)
│   │   └── __init__.py             # ComprehensiveSafetyManager (292 Zeilen)
│   │
│   ├── ui/                         # UI-Modul (16+ Dateien)
│   │   ├── main_window.py          # MainWindow (1202 Zeilen)
│   │   ├── settings_dialog.py      # SettingsDialog (300 Zeilen)
│   │   ├── keybindings.py          # 5 Tastenkürzel (96 Zeilen)
│   │   ├── config_panel.py         # Konfigurationsbereich (16 Zeilen)
│   │   ├── results_view.py         # Ergebnisse-Ansicht (17 Zeilen)
│   │   ├── file_table.py           # Dateitabelle (21 Zeilen)
│   │   ├── components/             # UI-Komponenten
│   │   │   ├── treemap_view.py     # Matplotlib-Treemap (455 Zeilen)
│   │   │   ├── squarify.py         # Reine-Python-Squarified-Treemap (320 Zeilen)
│   │   │   ├── drill_down.py       # Treemap-Drill-Down (263 Zeilen)
│   │   │   ├── virtual_treeview.py # Virtuelles Scrollen (177 Zeilen)
│   │   │   ├── skeleton.py         # Skeleton-Ladebildschirm (197 Zeilen)
│   │   │   └── status_bar.py       # Statusleiste (186 Zeilen)
│   │   ├── tabs/                   # GUI-Tabs
│   │   │   ├── diff_preview.py     # Vorher/Nachher-Diff (298 Zeilen)
│   │   │   ├── history_tab.py      # Prüfprotokoll + Wiederherstellung (566 Zeilen)
│   │   │   ├── models_tab.py       # Modellbrowser (414 Zeilen)
│   │   │   └── prompts_tab.py      # Prompt-Editor (405 Zeilen)
│   │   ├── themes/                 # Designs
│   │   │   └── modern_theme.py     # 6-Design-Manager (451 Zeilen)
│   │   └── animations/             # Animationen
│   │       └── smooth_progress.py  # 60fps-Fortschrittsbalken + Spinner (84 Zeilen)
│   │
│   ├── models/                     # Datenmodelle (3 Dateien)
│   │   ├── file_info.py            # FileInfo (52 Zeilen, __slots__)
│   │   ├── scan_result.py          # ScanResult (55 Zeilen)
│   │   └── analysis_result.py      # AnalysisResult, RiskLevel (76 Zeilen)
│   │
│   └── utils/                      # Hilfsfunktionen (2 Dateien)
│       ├── config_loader.py        # 3-stufige Kaskadenkonfiguration (737 Zeilen)
│       └── credential_store.py     # keyring-Schlüsselspeicher (238 Zeilen)
│
└── tests/                          # Tests (~30 Dateien)
    ├── test_scanner.py
    ├── test_analyzer.py
    ├── test_safety.py
    ├── test_router.py
    ├── test_models.py
    ├── test_import.py
    ├── test_ui.py
    ├── test_deep_search.py
    ├── demo_router.py
    └── ...
```

---

## Technologie-Stack

| Komponente | Technologie | Version |
|-----------|-------------|---------|
| **Sprache** | Python | >= 3.10 |
| **GUI-Framework** | customtkinter | >= 5.2.0 |
| **LLM-API-Client** | openai | >= 1.0.0 |
| **Sichere Löschung** | send2trash | >= 1.8.0 |
| **Visualisierung** | matplotlib | >= 3.7.0 |
| **Schlüsselspeicher** | keyring | >= 24.0.0 |
| **HTTP-Client** | requests | >= 2.28.0 |
| **Drag & Drop** | tkinterdnd2 | >= 0.4.2 (optional, Graceful Degradation) |
| **Datenbank** | sqlite3 | (Python-Built-in) |
| **Tests** | pytest | >= 7.4.0 |
| **Testabdeckung** | pytest-cov | >= 4.0.0 |
| **Build** | PyInstaller | (über build.py) |

---

## Häufig gestellte Fragen

### F: Kann ich das Tool ohne API-Schlüssel verwenden?

**A:** Ja! Das System unterstützt **Lazy Initialization** (verzögerte Initialisierung). Wenn kein API-Schlüssel konfiguriert ist, startet die Anwendung normal und verwendet automatisch die **Regel-Engine** mit 10 vordefinierten Bereinigungsregeln. Diese Regeln erkennen temporäre Dateien, Cache, Logs, Installationspakete und mehr — ohne dass eine Internetverbindung erforderlich ist.

### F: Wie erhalte ich einen API-Schlüssel?

**A:** Registrieren Sie sich bei einem der unterstützten Anbieter:

- **DeepSeek** (empfohlen): [https://platform.deepseek.com](https://platform.deepseek.com)
- **OpenAI**: [https://platform.openai.com](https://platform.openai.com)
- **Anthropic**: [https://console.anthropic.com](https://console.anthropic.com)
- **OpenRouter**: [https://openrouter.ai](https://openrouter.ai)
- **SiliconFlow**: [https://siliconflow.cn](https://siliconflow.cn)

### F: Gibt es kostenlose Modelle?

**A:** Ja, folgende Modelle sind kostenlos nutzbar:

- **OpenRouter**: `google/gemini-2.0-flash-exp:free`, `meta-llama/llama-3.2-3b-instruct:free`
- **SiliconFlow**: `deepseek-ai/DeepSeek-V3`, `Qwen/Qwen2.5-7B-Instruct`, `Qwen/Qwen2.5-14B-Instruct`
- **DeepSeek**: `deepseek-v4-flash` (sehr günstig, nahezu kostenlos)
- **Ollama**: Lokale Ausführung (`llama3.2`, `qwen2.5`) — völlig kostenlos, keine Internetverbindung erforderlich

### F: Wie wechsle ich die Routing-Strategie?

**A:** Programmgesteuert über die Python-API:

```python
from src.analyzer import LLMRouter, RoutingStrategy

router = LLMRouter(strategy=RoutingStrategy.COST)     # Kostenpriorität
router.set_strategy(RoutingStrategy.LATENCY)           # Geschwindigkeitspriorität
router.set_strategy(RoutingStrategy.FALLBACK)           # Fehlerübergabe
router.set_strategy(RoutingStrategy.MANUAL)             # Manuelle Auswahl
```

Oder über die Konfigurationsdatei `~/.wiztree-cli-agent/config.json`.

### F: Wie sicher ist die Löschung?

**A:** Das System implementiert eine **mehrschichtige Sicherheitsarchitektur**:

1. 38 geschützte Systempfade können niemals gelöscht werden (Windows-Systemverzeichnisse, Boot-Dateien, Benutzerprofile)
2. Jede Datei wird vor der Löschung validiert (Existenz, Zugriffsrechte, Sperrstatus)
3. Alle Zerstörungsoperationen werden in einer SQLite-Datenbank protokolliert
4. Die Löschung erfordert eine manuelle Bestätigung durch den Benutzer
5. Standardmäßig werden Dateien in den Papierkorb verschoben (Soft Delete via `send2trash`) — nicht endgültig gelöscht
6. Gelöschte Dateien können über das Prüfprotokoll wiederhergestellt werden

### F: Wie viele Dateien kann das Tool verarbeiten?

**A:** Dank **virtuellem Scrollen** und **Speicheroptimierung** (via `__slots__`) können über 100.000 Dateien problemlos verarbeitet werden. Ein Scan von 500.000 Dateien dauert typischerweise weniger als 5 Sekunden bei einem Speicherverbrauch unter 200 MB.

### F: Welche Betriebssysteme werden unterstützt?

**A:** Das Tool ist primär für **Windows** entwickelt (da WizTree CLI nur unter Windows läuft). Die GUI basiert auf `customtkinter` und funktioniert unter Windows, macOS und Linux — der Scankern (WizTree CLI) ist jedoch Windows-exklusiv.

---

## Lizenz

**MIT License**

Copyright (c) 2026 WizTree CLI Agent

Diese Software wird unter der MIT-Lizenz bereitgestellt. Die Lizenz gewährt uneingeschränkte Nutzungs-, Vervielfältigungs-, Änderungs- und Verteilungsrechte, sofern der Copyright-Hinweis und die Lizenzbestimmungen in allen Kopien oder wesentlichen Teilen der Software enthalten sind.

Der vollständige Lizenztext ist in der Datei `LICENSE` zu finden.

---

## Mitwirken

Beiträge zum Projekt sind willkommen! Bitte beachten Sie folgende Schritte:

1. Forken Sie das Repository
2. Erstellen Sie einen Feature-Branch (`git checkout -b feature/mein-feature`)
3. Committen Sie Ihre Änderungen (`git commit -m 'Neues Feature hinzugefügt'`)
4. Pushen Sie den Branch (`git push origin feature/mein-feature`)
5. Öffnen Sie einen Pull Request

### Entwicklung

```bash
# Entwicklungsabhängigkeiten installieren
pip install -r requirements.txt
pip install pytest pytest-cov

# Tests ausführen
pytest tests/ -v

# Code-Abdeckung prüfen
pytest tests/ --cov=src/ --cov-report=term-missing
```

### Dokumentation

- **ARCHITECTURE.md** — Gesamtarchitektur und Moduldesign
- **API_REFERENCE.md** — Vollständige API-Referenz
- **CONFIGURATION.md** — Konfigurationsleitfaden mit allen Providern und Strategien
- **DEVELOPMENT.md** — Entwicklerleitfaden, Build-Anleitung und Änderungsprotokoll
