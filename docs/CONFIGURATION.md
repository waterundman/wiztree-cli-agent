# WizTree CLI Agent — Configuration Guide

## API Key Setup

Set environment variables for LLM providers:

```bash
# Windows CMD
set DEEPSEEK_API_KEY=sk-your-key
set OPENAI_API_KEY=sk-your-key
set ANTHROPIC_API_KEY=sk-ant-your-key
set OPENROUTER_API_KEY=sk-your-key
set SILICONFLOW_API_KEY=sk-your-key

# Or use secure credential store (v1.2.0+):
# Via GUI: Settings → Credentials
# Via code: CredentialStore.store_api_key("deepseek", "sk-xxx")
```

**No API key?** System auto-degrades to RuleEngine (10 predefined rules).

## LLM Router Config

File: `config/llm_config.json` (auto-migrated to `~/.wiztree-cli-agent/config.json`)

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

## Supported Providers

| Provider | Env Variable | Base URL | Free Models |
|----------|-------------|----------|-------------|
| DeepSeek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` | deepseek-v4-flash |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1` | — |
| Anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com/v1` | — |
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | gemini-2.0-flash-exp:free |
| SiliconFlow | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` | DeepSeek-V3, Qwen2.5-7B |
| Ollama | — (local) | `http://localhost:11434/v1` | llama3.2, qwen2.5 |

## Routing Strategies

| Strategy | Enum | Behavior |
|----------|------|----------|
| Cost-first | `COST` | Picks cheapest model per request |
| Latency-first | `LATENCY` | Picks fastest responding provider |
| Fallback | `FALLBACK` | Auto-failover to next available provider |
| Manual | `MANUAL` | User-specified provider only |

```python
from src.analyzer import LLMRouter, RoutingStrategy

router = LLMRouter(strategy=RoutingStrategy.COST)
router.set_strategy(RoutingStrategy.LATENCY)
```

## 3-Tier Cascading Config (v1.2.0+)

```
1. Built-in defaults    (hardcoded in ConfigLoader)
2. User config          (~/.wiztree-cli-agent/config.json)
3. In-memory overrides  (runtime changes, not persisted)
```

Resolution order: `override > user > builtin`.

## WizTree Configuration

Default WizTree path: `W:\WizTree\WizTree64.exe` (customizable in config).

## Price Reference (per 1M tokens, as of 2026-05)

| Model | Input | Output |
|-------|-------|--------|
| DeepSeek V4 Flash | $0.14 | $0.28 |
| DeepSeek V4 Pro | $0.44 | $0.87 |
| GPT-4o-mini | $0.15 | $0.60 |
| Claude-3-haiku | $0.25 | $1.25 |

## Circuit Breaker

```
CLOSED (normal) → 3 failures → OPEN (reject) → 60s timeout → HALF_OPEN (test) → CLOSED
```

## OpenRouter Provider Routing (fine control)

```json
{
  "model": "deepseek/deepseek-v4-pro",
  "provider": {
    "order": ["DeepSeek", "Together", "Novita"],
    "allow_fallbacks": true
  }
}
```
