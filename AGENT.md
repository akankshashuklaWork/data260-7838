# Code Review Instructions for Model Client

## Task
Review the following code for:
- Correctness (does it do what it claims?)
- Token tracking accuracy
- Code quality and design patterns
- Potential bugs or edge cases

## Code to Review

### src/model_client.py
- ModelClient class initialization
- complete() method implementation
- Token estimation logic
- Conversation history management
- get_stats() method

### hw1_client.py
- 5-turn conversation loop
- Message formatting
- Statistics printing
- Error handling

## Review Format

Use BULLET POINTS ONLY. No prose.

### Correctness Issues
- [ ] Issue: [Specific problem]
  - Impact: [What breaks]
  - Fix: [How to fix]

### Design/Quality Issues
- [ ] Issue: [Specific problem]
  - Why it matters: [Explanation]
  - Suggestion: [Improvement]

### Token Tracking
- [ ] Are tokens estimated correctly?
- [ ] Is cumulative tracking accurate?
- [ ] Are all turns counted?

### Error Handling
- [ ] Is Ollama connection failure handled?
- [ ] Are message format errors caught?
- [ ] Are edge cases covered?

## Strictness Level
STRICT - this code should handle production use cases

## Durable Rental Housing Project Instructions

1. Project description: this repository manages rental housing listings and the HW6 memory service; responses must not invent a listing, price, availability date, or legal conclusion.
2. Technology stack: use Python, FastAPI, Pydantic, PyMongo, MongoDB, and the existing HW1 `src/model_client.py` adapter with the local `qwen2:7b` Ollama model for normal chat runs.
3. Coding conventions: keep application modules under the shared `code/` folder, use `snake_case`, type-annotate public functions, validate API input with Pydantic, and return JSON-safe MongoDB values.
4. Testing approach: use fixed messages and fixed probe criteria for reproducible checks; test observable behavior and validation status codes rather than exact model wording.
5. Memory handling: store durable facts only when they are explicit, preserve contradictory facts in a named resolution record, and never silently discard a conflict.
6. Prohibited actions: do not put secrets in the repository, do not call a paid hosted model, and do not modify existing application code during a verification run.
