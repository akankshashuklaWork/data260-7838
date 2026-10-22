# AI_USE.md

1. I used ChatGPT/Codex to help organize the implementation, explain framework details, and review the report structure. I wrote the assignment-specific code, selected the test cases, ran the local checks, and reviewed the saved results.
2. A local qwen2:7b run initially produced an invalid tool name (`search|detail|aggregate`) and later repeated search calls instead of completing the requested chain. The complete 20-attempt record is in `raw/part2_live_model_attempts.json`.
3. I detected the issue by validating each action against an exact JSON schema and by reading the saved trace. I also independently caught a token-test issue: changing only the final Base64URL character can leave decoded padding bits unchanged, so the invalid-token check now changes a significant header byte.
4. I tightened the accepted tool schemas, allow one specific repair prompt, stop after the fixed budget, and changed the invalid-token test. The fixed evaluation now reaches 20/20 successful repaired cases, while the live-model results remain recorded without alteration.
