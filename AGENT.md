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
