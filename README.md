# DATA 260 Homework 1: Building AI Agents with LLMs

A project about building intelligent AI agents that analyze text using Large Language Models.

**What you'll build:**
- Multi-agent AI pipeline (Planner → Reviewer → Finalizer)
- Non-determinism testing (temperature effects on consistency)
- Token accounting and cost tracking
- Reusable model client for any LLM

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Ollama (download from https://ollama.ai)
- ~4GB disk space

### Setup
```bash
# Start Ollama in one terminal
ollama serve
ollama pull qwen2:7b

# In another terminal
cd /Users/akanksha/Downloads/data260-7838/code
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run the Code
```bash
# Part 2: Multi-agent pipeline
python agents_demo.py

# Part 4: Token tracking demo
python hw1_client.py

# Part 3: View non-determinism results
cat ../reports/hw01/METRICS.md
```

---

## 📂 Project Structure

```
📁 code/
├── agents_demo.py          ← Part 2: Multi-agent pipeline
├── hw1_client.py           ← Part 4: Token tracking
├── requirements.txt
└── web_application/        ← Part 1: Web form

📁 src/
└── model_client.py         ← Part 4: LLM adapter

📁 reports/hw01/
├── METRICS.md              ← Part 3: Non-determinism results
├── AI_USE.md
└── raw/nondeterminism_results.json
```

---

## 📖 Parts Overview

### Part 1: Web Interface ✅
A complete web form for submitting rental property listings.

**Features:**
- Property title input (required)
- Property location input (required)
- Submitter email input (required, validated)
- Property description textarea (required, min 25 characters)
- Property category dropdown (Apartment, House, Condo, Townhouse)
- Terms and conditions checkbox
- Form validation (client-side)
- Displays successful submissions in a list

**Files:**
- `code/web_application/index.html` - Form structure
- `code/web_application/styles.css` - Styling
- `code/web_application/script.js` - Form logic and validation
- `code/web_application/tests/` - Test suite

**To view:** Open `code/web_application/index.html` in a browser

### Part 2: Multi-Agent Pipeline
Three agents analyze apartment listings:
- **Planner**: Extract 3 tags + summary
- **Reviewer**: Improve if needed
- **Finalizer**: Enforce rules (exactly 3 tags, ≤25 words)

Example output:
```json
{
  "tags": ["2BR Apartment", "Downtown San Jose", "Pet-friendly"],
  "summary": "Spacious 2BR with city views and amenities",
  "word_count": 16,
  "source": "Reviewer"
}
```

### Part 3: Non-Determinism Testing
Tests how temperature affects AI behavior across 40 real runs (20 at each temperature):
- Temp 0.0: 1 distinct tag set across all 20 runs (deterministic)
- Temp 0.7: 14 distinct tag sets across 20 runs (creative)
- **Finding**: Higher temp = More variety but less consistency

Results in `reports/hw01/METRICS.md`, full explanation in `reports/hw01/report.pdf`

### Part 4: Token Accounting
Demonstrates why AI conversations get expensive. Real numbers from a 5-turn conversation:
- Per-turn input tokens: 56, 462, 764, 1094, 1652 (turns 1-5) - growing every turn
- Cumulative after turn 3: 1282 input / 987 output tokens
- Cumulative after turn 5: 4028 input / 2187 output tokens
- Each turn resends the entire conversation history, so nothing already sent is ever removed

---

## 🧠 Key Concepts

**Temperature**: Controls AI creativity (0.0=deterministic, 0.7=balanced, 2.0=creative)

**Tokens**: Small pieces of text (~1 token per 4 chars), cost money on cloud AI

**Agents**: Specialized AI pieces working together (Planner, Reviewer, Finalizer)

**Context Window**: Maximum tokens an AI can remember (~8192 for qwen2:7b)

---

## 🚀 Running Each Part

### Part 1: Web Form
```bash
open code/web_application/index.html
# Fill form to submit rental listings
```

### Part 2: Multi-Agent Pipeline
```bash
cd code
python agents_demo.py  # ~30-60 seconds
```

### Part 3: Non-Determinism Results
```bash
cat reports/hw01/METRICS.md  # Already run
```

### Part 4: Token Tracking
```bash
cd code
python hw1_client.py  # ~10-20 seconds
```

---

## 🛠️ Troubleshooting

**Python version wrong?**
```bash
python3.11 --version
brew install python@3.11  # if missing
```

**Ollama not running?**
```bash
ollama serve
curl http://localhost:11434/api/tags  # test it
```

**Module not found?**
```bash
cd code
source venv/bin/activate
python hw1_client.py
```
(hw1_client.py inserts the repo root into sys.path itself, so no manual PYTHONPATH is needed.)

---

## Q&A: Understanding Tokens and Context (Part 4)

**Why is prior conversation context resent with every turn?**
The model is stateless - it has no memory between separate calls. The only way it responds consistently with earlier turns is if the caller resends the full prior conversation (system prompt, all previous messages) alongside the new one every time.

**How is a system prompt different from a user message?**
A system prompt sets the assistant's behavior/rules and is written by the application. A user message is the actual question from the person using it. Both count as input tokens and get resent every turn, but one is an instruction to the model and the other is data for the model to respond to.

**Why do input tokens grow over a conversation?**
Each turn's input is the system prompt plus every prior message plus the new message - nothing already sent is ever removed. In this project's real 5-turn run, per-turn input tokens were 56, 462, 764, 1094, then 1652 - climbing every turn because turn N's input contains all of turns 1 through N-1.

**What eventually limits that growth?**
The model's context window is the hard limit (a fixed max tokens per call). Before that, cost and latency are practical limits - more tokens per turn means slower responses and higher cost, which is why production systems often truncate or summarize history instead of resending an ever-growing transcript.

---

## 📊 Files Reference

| File | Purpose |
|------|---------|
| `code/agents_demo.py` | Run multi-agent pipeline |
| `code/hw1_client.py` | Run token tracking demo |
| `src/model_client.py` | Reusable LLM adapter |
| `reports/hw01/METRICS.md` | Non-determinism test results |
| `AGENT.md` | Code review guidelines |
| `DOMAIN_SCHEMA.md` | Rental listing structure |

---

**Version**: Homework 1, DATA 260  
**Domain**: Rental Housing Listings  
**Python**: 3.11+  
**Model**: qwen2:7b
