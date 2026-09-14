# AI Use Disclosure

1. AI assistance was used to write planner_node and reviewer_node (the prompts and the calls into the model adapter), the experiment runner (run_hw2_experiments.py), and the metrics analysis script (analyze_hw2_experiments.py). AI assistance was also used to draft report.docx/report.pdf: it drove the running application through a scripted browser to capture screenshots of every required UI state, ran the offline test, one real graph invocation, and a temporary Step 6 self-correction demo. I wrote the AgentState TypedDict and the PlannerOutput Pydantic schema myself, along with supervisor_node and router_logic (the turn counting and the routing decisions). For the report, I reviewed and edited the drafted text, chose which screenshots to include and how each part should be presented, wrote some of the explanations myself, and checked the finished report against the HW2 assignment line by line before accepting it.

2. The first version of PlannerOutput that I wrote did not yet enforce the Part 4 contract: it accepted whatever JSON shape came back without checking that tags had exactly three entries, each 3-30 characters, or that summary stayed under 25 words.

3. I found the gap by comparing my schema against the HW2 Part 4 requirements line by line, and confirmed it by adding an offline test that feeds the Planner an invalid response and checks that the graph catches it instead of accepting it.

4. I added field_validator methods to PlannerOutput to enforce the tag count/length and word-count rules, and confirmed the validation error gets fed back into reviewer_feedback so the Supervisor routes back to the Planner instead of silently accepting bad output. The offline test and the recorded experiments verify this now works.
