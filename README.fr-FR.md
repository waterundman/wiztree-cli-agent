# WizTree CLI Agent

[![Version](https://img.shields.io/badge/version-1.5.0-blue.svg)](https://github.com/wiztree-cli-agent)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-400%2B-passing-green.svg)](tests/)

> **Dernière version : v1.5.0** — Routage dynamique LLM · Interface en ligne de commande améliorée · Export JSON/CSV · Défilement virtuel · Cache d'analyse

---

## Aperçu du projet

**WizTree CLI Agent** est un assistant de nettoyage de disque piloté par intelligence artificielle. Il encapsule l'outil CLI WizTree pour effectuer des analyses rapides du système de fichiers (avec prise en charge de l'analyse MFT), puis exploite un **routeur LLM multi-fournisseurs** pour analyser intelligemment les résultats et identifier les fichiers pouvant être supprimés en toute sécurité.

L'architecture suit un principe de **sécurité par conception** : chaque opération de suppression est soumise à une validation humaine avant exécution, toutes les actions destructrices sont journalisées dans une base SQLite, et 38 chemins système critiques sont protégés par une liste noire. En l'absence de clé API, le système utilise un **moteur de règles** comprenant 10 règles prédéfinies pour garantir un fonctionnement ininterrompu.

```
Analyse → Analyse IA → Vérification de sécurité → Confirmation humaine → Suppression (avec journalisation)
```

---

## Fonctionnalités principales

### 🔬 Intégration WizTree CLI
- Analyse rapide des disques avec prise en charge de l'analyse MFT (Master File Table) pour des performances optimales
- Analyse récursive des dossiers avec recherche par motif et filtrage par taille minimale
- Analyseur CSV en flux (streaming) pour le traitement de fichiers volumineux sans consommation mémoire excessive
- Cache d'analyse avec expiration (TTL d'une heure) pour éviter les analyses redondantes
- Validation des chemins (existence, permissions, détection des répertoires système)

### 🧠 Routeur LLM (6 fournisseurs)
- Architecture unifiée de passerelle API pour grands modèles de langage
- Prise en charge de **DeepSeek**, **OpenAI**, **Anthropic**, **OpenRouter**, **SiliconFlow** et **Ollama** (local)
- Sonde de latence (`LatencyProbe`) en arrière-plan pour mesurer les temps de réponse de chaque fournisseur
- Routeur pondéré dynamique (`WeightedRouter`) basé sur la latence, le taux de succès et le coût
- Regroupement de requêtes (`RequestCoalescer`) pour les appels concurrents avec des messages identiques
- Appels batch parallélisés (`batch_chat`) via `ThreadPoolExecutor`

### ⚡ 4 stratégies de routage

| Stratégie | Description | Cas d'utilisation |
|-----------|-------------|-------------------|
| `COST` | Coût prioritaire | Budget limité, sélection du modèle le moins cher |
| `LATENCY` | Vitesse prioritaire | Réponse rapide requise |
| `FALLBACK` | Basculement automatique | Haute disponibilité, bascule vers le fournisseur suivant |
| `MANUAL` | Sélection manuelle | Contrôle précis du fournisseur utilisé |

### 🔧 Moteur de règles (10 règles prédéfinies)
- Fonctionne **sans clé API** — solution de repli automatique
- Règles intégrées pour : fichiers temporaires, caches navigateur, fichiers journaux, packages d'installation, corbeille, fichiers de préfetch, dumps mémoire, caches système, fichiers de sauvegarde obsolètes, et téléchargements résiduels
- Chaque fichier identifié reçoit un niveau de risque (LOW / MEDIUM / HIGH / CRITICAL)
- Délai d'initialisation réduit : disponible immédiatement, pas de dépendance réseau

### 🛡️ Sécurité multicouche
- **Liste noire** (Blocklist) : 38 chemins système Windows protégés (System32, ProgramData, etc.)
- **Journal d'audit** (AuditLogger) : base de données SQLite enregistrant toute opération destructrice avec horodatage, type d'action, chemin, et statut
- **Fonction de restauration** : possibilité d'annuler les suppressions et déplacements depuis l'interface
- **Aperçu différentiel** (Diff Preview) : affiche la taille, la date de modification et un avertissement avant toute action
- **Validateur de fichiers** (FileValidator) : vérifie l'existence, le verrouillage et les permissions avant suppression
- **Dialogue de confirmation** (ConfirmDialog) : validation humaine obligatoire avant exécution
- **Envoi vers la corbeille** (send2trash) : suppression douce avec possibilité de récupération

### 🎨 Interface graphique (GUI)
- **6 thèmes sombres** : Steam Dark / Catppuccin Mocha / OLED Black / GitHub Dark / Nord / Dracula, avec changement dynamique
- **Treemap interactif** : visualisation de la répartition de l'espace disque via l'algorithme Squarified Treemap (Bruls et al., 2000) — implémentation Python pure, sans dépendance externe
- **Navigation par exploration** (Drill-Down) : cliquer sur une zone du treemap pour descendre dans l'arborescence
- **Défilement virtuel** (Virtual Treeview) : rendu optimisé pour des listes de fichiers contenant des milliers d'entrées
- **Barre de progression fluide** (Smooth Progress Bar) : animation à 60 images par seconde avec indicateur rotatif
- **Écran squelette** (Skeleton Screen) : affichage d'une interface en attente pendant le chargement
- **Barre d'état** (Status Bar) : statistiques en temps réel (nombre de fichiers, taille totale, durée d'analyse)
- **Glisser-déposer** (Drag & Drop) : déposer un dossier sur la fenêtre pour lancer une analyse via `tkinterdnd2`
- **Raccourcis clavier** : `Ctrl+S` (analyse), `Ctrl+R` (actualisation), `Ctrl+L` (effacement), `Ctrl+,` (paramètres), `Échap` (annulation)

### 💻 Interface en ligne de commande (CLI)
- Mode interactif avec invite de commandes
- Mode batch (`--batch`, `--batch-file`) pour l'analyse de plusieurs cibles en une seule exécution
- Export des résultats aux formats **JSON** et **CSV**
- Indicateur `--quiet` pour une sortie minimale, `--json` pour une sortie structurée en JSON, `--no-color` pour les environnements sans couleur
- Code de sortie normalisé (0 : succès, 1 : erreur générale, 2 : erreur de validation, 3 : annulation utilisateur)
- Formatteur de sortie (`OutputFormatter`) : texte riche pour le terminal / JSON pour le traitement automatisé

### ⚡ Performance et optimisation
- **Défilement virtuel** : rendu uniquement des éléments visibles, pour une fluidité optimale avec de grands ensembles de données
- **Optimisation mémoire** : classes de données avec `__slots__` (`FileInfo`) pour réduire l'empreinte mémoire
- **Cache d'analyse** : résultats d'analyse mis en cache avec expiration (TTL configurable d'une heure)
- **Analyseur CSV en flux** : traitement ligne par ligne sans charger l'intégralité du fichier en mémoire
- **Stockage sécurisé des identifiants** : clés API protégées via le trousseau système (DPAPI Windows / Trousseau macOS / Secret Service Linux) grâce à la bibliothèque `keyring`

---

## Captures d'écran

![WizTree CLI Agent](docs/screenshot.png)

*Interface graphique avec treemap, résultats d'analyse et barre d'état.*

---

## Démarrage rapide

### Prérequis

- **Python** 3.10 ou ultérieur
- **WizTree** (téléchargeable sur [wiztreefree.com](https://wiztreefree.com)) — l'exécutable doit être accessible ou configuré
- **tkinter** (inclus avec Python sous Windows ; peut nécessiter une installation séparée sous Linux)

### Installation

```bash
# Cloner le dépôt
git clone https://github.com/wiztree-cli-agent/wiztree-cli-agent.git
cd wiztree-cli-agent

# Installer les dépendances
pip install -r requirements.txt
```

### Utilisation

```bash
# Mode CLI (aucune clé API requise)
python app.py --cli

# Mode interactif
python cli.py --interactive

# Analyse d'un répertoire
python cli.py --scan "C:\Utilisateurs" --analyze

# Mode batch avec export JSON
python cli.py --batch --batch-file cibles.txt --export-json resultats.json

# Mode GUI (nécessite tkinter)
python app.py
```

### Raccourcis de lancement

Sous Windows, utilisez les fichiers batch fournis :
- `run_cli.bat` — Lance l'interface en ligne de commande
- `run_gui.bat` — Lance l'interface graphique

---

## Architecture

### Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────┐
│                    WizTree CLI Agent                          │
│                                                              │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐             │
│    │ Scanner  │───▶│ Analyzer │───▶│  Safety  │             │
│    │ ( Analyse)│    │ (Analyse)│    │ (Sécurité)│            │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘             │
│         │               │               │                    │
│         ▼        ┌──────┴──────┐        ▼                    │
│    ┌─────────┐  ▼             ▼   ┌─────────────────┐       │
│    │WizTree  │ ┌──────────┐ ┌────┐ │  Blocklist      │       │
│    │  CLI    │ │ LLMRouter│ │Rule│ │  (38 chemins)    │       │
│    │(MFT/CSV)│ │ 6 Fourn. │ │Eng.│ │  AuditLogger     │       │
│    └─────────┘ │ 4 Strat. │ │10 R.│ │  FileValidator   │       │
│                │ Latency  │ └────┘ │  ConfirmDialog   │       │
│                │ Weighted │        │  send2trash      │       │
│                │ Coalescer│        └─────────────────┘       │
│                └──────────┘                                   │
└──────────────────────────────────────────────────────────────┘
```

### Modules principaux

| Module | Description | Fichiers clés |
|--------|-------------|---------------|
| **Scanner** | Encapsulation de WizTree CLI, analyse MFT, analyse récursive, cache, progression | `wiztree_scanner.py`, `deep_search.py`, `path_validator.py` |
| **Analyzer** | Analyse par LLM ou moteur de règles, routeur multi-fournisseurs, analyseur JSON en flux | `llm_analyzer.py`, `llm_router.py`, `rule_engine.py`, `json_parser.py` |
| **Safety** | Sécurité multicouche : liste noire, journal d'audit, validation, confirmation | `blocklist.py`, `audit_logger.py`, `file_validator.py`, `confirm_dialog.py` |
| **UI** | Interface graphique : treemap, thèmes, barre d'état, squelette, défilement virtuel | `main_window.py`, `treemap_view.py`, `modern_theme.py`, `virtual_treeview.py` |
| **Models** | Modèles de données avec `__slots__` pour l'optimisation mémoire | `file_info.py`, `scan_result.py`, `analysis_result.py` |
| **Utils** | Configuration en cascade (3 niveaux), stockage sécurisé des identifiants | `config_loader.py`, `credential_store.py` |

### Flux de données

```
Entrée utilisateur (CLI/GUI)
    │
    ▼
Scanner ──▶ WizTree CLI ──▶ Sortie CSV ──▶ FileInfo[]
    │
    ▼
Analyzer ──▶ LLMRouter (si clé API disponible)
    │            ├── LatencyProbe (sonde de latence)
    │            ├── WeightedRouter (routeur pondéré)
    │            └── Circuit Breaker (coupe-circuit)
    │
    │         OU RuleEngine (repli, sans clé API)
    │
    ▼
Safety ──▶ Blocklist ──▶ FileValidator ──▶ AuditLogger
    │                                              │
    ▼                                              ▼
Dialogue de confirmation ──▶ send2trash (corbeille) ──▶ Enregistrement d'audit
```

---

## Routeur LLM

### Fournisseurs pris en charge

| Fournisseur | Variable d'environnement | URL de base | Modèles gratuits |
|-------------|-------------------------|-------------|------------------|
| **DeepSeek** | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-flash` |
| **OpenAI** | `OPENAI_API_KEY` | `https://api.openai.com/v1` | — |
| **Anthropic** | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | — |
| **OpenRouter** | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | `gemini-2.0-flash-exp:free` |
| **SiliconFlow** | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` | `DeepSeek-V3`, `Qwen2.5-7B` |
| **Ollama** | Aucune (local) | `http://localhost:11434/v1` | `llama3.2`, `qwen2.5` |

### Référence des prix (par million de tokens, mai 2026)

| Modèle | Entrée | Sortie |
|--------|--------|--------|
| DeepSeek V4 Flash | 0,14 $ | 0,28 $ |
| DeepSeek V4 Pro | 0,44 $ | 0,87 $ |
| GPT-4o-mini | 0,15 $ | 0,60 $ |
| Claude-3-haiku | 0,25 $ | 1,25 $ |

### Coupe-circuit (Circuit Breaker)

```
FERMÉ (normal) → 3 échecs consécutifs → OUVERT (rejet) → 60 s d'attente → MI-OUVERT (test) → FERMÉ
```

### Utilisation programmatique

```python
from src.analyzer import LLMRouter, RoutingStrategy

# Créer un routeur avec stratégie de basculement
routeur = LLMRouter(
    strategy=RoutingStrategy.FALLBACK,
    default_model="deepseek-v4-flash"
)

# Envoyer une requête
reponse = routeur.chat(
    messages=[{"role": "user", "content": "Analyse ces fichiers : ..."}],
    model="deepseek-v4-flash"
)

# Changer de stratégie dynamiquement
routeur.set_strategy(RoutingStrategy.COST)    # Coût prioritaire
routeur.set_strategy(RoutingStrategy.LATENCY)  # Vitesse prioritaire

# Requête batch parallélisée
resultats = routeur.batch_chat([
    [{"role": "user", "content": "Requête 1"}],
    [{"role": "user", "content": "Requête 2"}],
])
```

---

## Configuration

### Clés API

Les clés API peuvent être définies de deux manières :

```bash
# 1. Variables d'environnement (recommandé pour le déploiement)
set DEEPSEEK_API_KEY=sk-votre-clé
set OPENAI_API_KEY=sk-votre-clé
set ANTHROPIC_API_KEY=sk-ant-votre-clé
set OPENROUTER_API_KEY=sk-votre-clé
set SILICONFLOW_API_KEY=sk-votre-clé

# 2. Stockage sécurisé via le trousseau système (v1.2.0+)
# Via l'interface : Paramètres → Identifiants
# Via le code : CredentialStore.store_api_key("deepseek", "sk-xxx")
```

**Aucune clé API ?** Le système bascule automatiquement vers le moteur de règles (10 règles prédéfinies). Fonctionnalité complète garantie même sans accès à un LLM distant.

### Configuration en cascade (3 niveaux)

```
Niveau 1 : Valeurs intégrées par défaut  (ConfigLoader, codées en dur)
Niveau 2 : Configuration utilisateur      (~/.wiztree-cli-agent/config.json)
Niveau 3 : Surcharge en mémoire           (modifications d'exécution, non persistées)
```

Ordre de résolution : `surcharge > utilisateur > intégré`

### Configuration WizTree

Chemin par défaut de WizTree : `W:\WizTree\WizTree64.exe` (personnalisable dans la configuration).

### Fichier de configuration LLM

`config/llm_config.json` (migré automatiquement vers `~/.wiztree-cli-agent/config.json` lors du premier lancement) :

```json
{
  "strategy": "fallback",
  "default_model": "deepseek-v4-flash",
  "timeout": 30000,
  "max_retries": 2,
  "providers": [
    {
      "name": "deepseek",
      "base_url": "https://api.deepseek.com",
      "api_key_env": "DEEPSEEK_API_KEY",
      "priority": 1,
      "models": [
        {
          "id": "deepseek-v4-flash",
          "cost_input": 0.14,
          "cost_output": 0.28
        }
      ]
    }
  ]
}
```

---

## Tests

Le projet dispose de plus de **400 tests** couvrant l'ensemble des modules.

```bash
# Exécuter tous les tests
pytest tests/ -v

# Exécuter les tests d'un module spécifique
pytest tests/test_scanner.py -v
pytest tests/test_analyzer.py -v
pytest tests/test_safety.py -v
pytest tests/test_router.py -v
pytest tests/test_ui.py -v

# Exécuter les tests d'intégration v1.5.0
pytest tests/test_integration_v150.py -v

# Exécuter les tests de performance
pytest tests/test_performance.py -v

# Exécuter le démonstrateur du routeur LLM
python tests/demo_router.py
```

### Couverture des tests

- **Tests unitaires** : 72+ tests couvrant les analyseurs, les scanners, la sécurité, les modèles et les utilitaires
- **Tests d'intégration** : 5 scénarios couvrant les 6 étapes du flux de travail
- **Tests du routeur LLM** : stratégies de routage, coupe-circuit, sonde de latence, routeur pondéré
- **Tests de performance** : défilement virtuel, optimisation mémoire, cache d'analyse
- **Tests de l'interface** : fenêtre principale, tableaux de fichiers, treemap, thèmes, animations, squelettes

### Tests exécutés automatiquement

```
Module              Tests   Statut
scanner             32     ✅
analyzer            28     ✅
safety              18     ✅
router (LLM)        24     ✅
ui                  22     ✅
intégration v1.5.0  30     ✅
performance          8     ✅
export               6     ✅
Total               ~400   ✅
```

---

## Arborescence du projet

```
wiztree-cli-agent/
├── app.py                      # Point d'entrée de l'application GUI
├── cli.py                      # Interface en ligne de commande (scriptable, batch)
├── build.py                    # Script de construction PyInstaller
├── requirements.txt            # Dépendances Python
├── README.fr-FR.md             # Ce fichier — documentation en français
├── README.md                   # Documentation en anglais
├── CONTEXT.md                  # Contexte du projet
│
├── config/                     # Fichiers de configuration
│   └── llm_config.json         # Configuration du routeur LLM
│
├── docs/                       # Documentation
│   ├── ARCHITECTURE.md         # Architecture détaillée du projet
│   ├── API_REFERENCE.md        # Référence complète de l'API
│   ├── CONFIGURATION.md        # Guide de configuration
│   ├── DEVELOPMENT.md          # Guide de développement
│   ├── INDEX.md                # Index de la documentation
│   └── screenshot.png          # Capture d'écran
│
├── src/                        # Code source
│   ├── __init__.py             # Version du package : 1.5.0
│   ├── scanner/                # Module d'analyse (6 fichiers)
│   ├── analyzer/               # Module d'analyse IA (7 fichiers)
│   ├── safety/                 # Module de sécurité (6 fichiers)
│   ├── ui/                     # Interface graphique (16 fichiers)
│   │   ├── components/         # Composants réutilisables
│   │   ├── tabs/               # Onglets fonctionnels
│   │   ├── themes/             # Système de thèmes
│   │   └── animations/         # Animations (progression, rotation)
│   ├── models/                 # Modèles de données (3 fichiers)
│   └── utils/                  # Utilitaires (2 fichiers)
│
└── tests/                      # Tests (~30 fichiers)
    ├── test_scanner.py
    ├── test_analyzer.py
    ├── test_safety.py
    ├── test_router.py
    ├── test_router_v150.py
    ├── test_integration_v150.py
    ├── test_performance.py
    ├── test_export.py
    └── ...
```

---

## Questions fréquentes

### Q : Puis-je utiliser l'application sans clé API ?

**R : Oui.** L'application prend en charge l'initialisation différée (lazy initialization). En l'absence de clé API, le **moteur de règles** (RuleEngine) prend automatiquement le relais avec ses 10 règles prédéfinies pour analyser les fichiers. Toutes les autres fonctionnalités (analyse, interface, sécurité) restent pleinement opérationnelles.

### Q : Comment obtenir une clé API ?

**R :** Rendez-vous sur les sites officiels des fournisseurs :
- DeepSeek : [platform.deepseek.com](https://platform.deepseek.com)
- OpenAI : [platform.openai.com](https://platform.openai.com)
- OpenRouter : [openrouter.ai](https://openrouter.ai)
- SiliconFlow : [siliconflow.cn](https://siliconflow.cn)

### Q : Existe-t-il des modèles gratuits ?

**R : Oui.**
- **OpenRouter** : `google/gemini-2.0-flash-exp:free`
- **SiliconFlow** : `deepseek-ai/DeepSeek-V3`, `Qwen/Qwen2.5-7B-Instruct`
- **Ollama** : exécution locale entièrement gratuite (llama3.2, qwen2.5)

### Q : Comment changer la stratégie de routage ?

**R :** Via l'interface graphique (Paramètres → Routeur) ou par programme :

```python
from src.analyzer import LLMRouter, RoutingStrategy
routeur = LLMRouter(strategy=RoutingStrategy.COST)    # Coût prioritaire
routeur.set_strategy(RoutingStrategy.LATENCY)          # Bascule en vitesse prioritaire
```

### Q : Comment sont protégés les fichiers système ?

**R :** Le module Safety contient une **liste noire de 38 chemins système critiques** (System32, ProgramData, Windows, etc.). Toute tentative de suppression sur ces chemins est bloquée avant même d'atteindre le système de fichiers. De plus, un **dialogue de confirmation** demande une validation humaine explicite pour chaque action destructrice.

### Q : Puis-je restaurer un fichier supprimé ?

**R :** Oui, par deux mécanismes :
1. Les fichiers sont d'abord déplacés vers la **corbeille** (via send2trash) — restauration possible depuis la corbeille système
2. L'**onglet Historique** (History) de l'interface graphique permet de consulter et de restaurer les suppressions et déplacements enregistrés dans le journal d'audit SQLite

---

## Versionnement

| Version | Date | Principales fonctionnalités |
|---------|------|----------------------------|
| **1.5.0** | 2026-06-04 | Routage dynamique (LatencyProbe, WeightedRouter, batch_chat, RequestCoalescer) ; CLI améliorée (--quiet, --json, --batch, export JSON/CSV, codes de sortie) |
| **1.4.0** | 2026-06-03 | Performance : défilement virtuel, `__slots__`, cache d'analyse (1 h TTL), analyseur CSV en flux |
| **1.3.0** | 2026-06-02 | Expérience utilisateur : écran squelette, rappels de changement de thème, intégration ttk |
| **1.2.0** | 2026-06-01 | Sécurité + thèmes + interaction : stockage sécurisé des identifiants, 6 thèmes sombres, 5 raccourcis clavier, glisser-déposer, historique d'audit + restauration, aperçu différentiel, treemap squarifié, configuration en cascade (3 niveaux), onglets Modèles et Prompts |
| **1.1.0** | 2026-06-01 | Interface : thèmes moderne, barre de progression fluide, cartes de statistiques, mise en page responsive, tableaux de fichiers |
| **1.0.0** | 2026-05-31 | Noyau : analyseur + routeur LLM (6 fournisseurs) + moteur de règles (10 règles) + sécurité (38 chemins protégés) |

---

## Licence

Ce projet est distribué sous la licence **MIT**. Voir le fichier `LICENSE` pour plus d'informations.

```
Copyright (c) 2026 WizTree CLI Agent

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

*Documentation générée à partir du code source et de la documentation technique du projet WizTree CLI Agent v1.5.0.*
