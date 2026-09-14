# AI Use Disclosure

1. AI assistance was used to structure the LangGraph state, implement the Supervisor/Planner/Reviewer routing, write the experiment runner, and create the metrics analysis script. AI assistance was also used to assemble report.docx/report.pdf: it drove the running application (via a headless, scripted browser) to capture real screenshots of every required UI state, ran the offline test, one real graph invocation, and a temporary Step 6 self-correction demo to capture their real console output, and wrote the report text from the measured results. The student selected the domain input, reviewed the graph flow against the assignment diagram, ran the local experiments, and reviewed the measured results and the assembled report before submission.

2. The first implementation of the graph did not yet include the Part 4 Pydantic validation contract. It was identified as incomplete before running the experiments.

3. The gap was detected by comparing the implementation against the HW2 Part 4 requirements and by adding an offline test that returns invalid Planner JSON before a valid retry.

4. The Planner now validates output with Pydantic, stores validation errors in shared state, and retries through the Supervisor/Planner loop. The offline test and the recorded experiments verify the behavior.
