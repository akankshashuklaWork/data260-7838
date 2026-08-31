#!/usr/bin/env python3
"""
Part 2: Agentic AI - Planner → Reviewer → Finalizer Flow
Domain: Rental Housing Listings (DOMAIN_ID 6)
Uses Ollama with local LLM to generate tags and summary
"""

import json
import sys
import time
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

# Configuration
MODEL_NAME = "qwen2:7b"  # or qwen3:8b if hardware supports
OLLAMA_BASE_URL = "http://localhost:11434"
TEMPERATURE = 0.7

def create_planner_agent(temperature: float = TEMPERATURE) -> ChatOllama:
    """Create the Planner agent."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        format="json"
    )

def create_reviewer_agent(temperature: float = TEMPERATURE) -> ChatOllama:
    """Create the Reviewer agent."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=temperature,
        format="json"
    )

def planner_step(title: str, content: str, temperature: float = TEMPERATURE, verbose: bool = True) -> dict:
    """
    Planner Agent: Generates initial tags and summary from title and content.
    Returns a JSON object with tags and summary.
    """
    planner = create_planner_agent(temperature)

    system_prompt = SystemMessage(content="""You are a content analyst. Analyze the given title and content to generate:
1. Exactly 3 topical tags (relevant keywords from the content, not generic)
2. A one-sentence summary (maximum 25 words)

You MUST output valid JSON with this exact structure:
{
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "your summary here",
  "reasoning": "brief explanation of your choices"
}

Focus on what the content actually talks about, not generic domain terms.""")

    user_prompt = HumanMessage(content=f"""Title: {title}

Content: {content}

Analyze this and generate 3 tags and a summary. Output ONLY valid JSON, no other text.""")

    response = planner.invoke([system_prompt, user_prompt])

    try:
        result = json.loads(response.content)
        if verbose:
            print("\n" + "="*80)
            print("PLANNER OUTPUT:")
            print("="*80)
            print(json.dumps(result, indent=2))
        return result
    except json.JSONDecodeError:
        if verbose:
            print(f"ERROR: Planner output is not valid JSON:\n{response.content}")
        return {"tags": [], "summary": "", "reasoning": "Failed to parse"}

def reviewer_step(title: str, content: str, planner_output: dict, temperature: float = TEMPERATURE, verbose: bool = True) -> dict:
    """
    Reviewer Agent: Reviews and potentially improves the Planner's tags and summary.
    Returns a JSON object indicating changes made.
    """
    reviewer = create_reviewer_agent(temperature)

    system_prompt = SystemMessage(content="""You are a quality reviewer. Review the tags and summary provided by the Planner:
1. Check if tags are relevant and specific (not generic)
2. Verify the summary is ≤25 words and captures the essence
3. Suggest improvements if needed

Output valid JSON with this structure:
{
  "tags": ["tag1", "tag2", "tag3"],
  "summary": "your summary here",
  "changed": true/false,
  "explanation": "what changed and why, or 'no changes needed'"
}

Keep tags and summary only if they're good. Otherwise, improve them based on the content.""")

    planner_tags = json.dumps(planner_output.get("tags", []))
    planner_summary = planner_output.get("summary", "")

    user_prompt = HumanMessage(content=f"""Title: {title}

Content: {content}

Planner's tags: {planner_tags}
Planner's summary: {planner_summary}

Review these. Output ONLY valid JSON with improved tags/summary if needed.""")

    response = reviewer.invoke([system_prompt, user_prompt])

    try:
        result = json.loads(response.content)
        if verbose:
            print("\n" + "="*80)
            print("REVIEWER OUTPUT:")
            print("="*80)
            print(json.dumps(result, indent=2))
        return result
    except json.JSONDecodeError:
        if verbose:
            print(f"ERROR: Reviewer output is not valid JSON:\n{response.content}")
        return planner_output

def finalizer_step(planner_output: dict, reviewer_output: dict, verbose: bool = True) -> dict:
    """
    Finalizer: Combines Planner and Reviewer outputs into final JSON.
    Ensures exactly 3 tags and ≤25 word summary.
    """
    if verbose:
        print("\n" + "="*80)
        print("FINALIZER STEP:")
        print("="*80)

    # Use Reviewer output if it changed something meaningful, otherwise use Planner
    if reviewer_output.get("changed", False) and reviewer_output.get("tags"):
        final_tags = reviewer_output["tags"][:3]  # Ensure exactly 3
        final_summary = reviewer_output["summary"]
        source = "Reviewer"
    else:
        final_tags = planner_output["tags"][:3]  # Ensure exactly 3
        final_summary = planner_output["summary"]
        source = "Planner"

    # Validate summary length
    word_count = len(final_summary.split())
    if word_count > 25:
        final_summary = " ".join(final_summary.split()[:25])

    final_output = {
        "tags": final_tags,
        "summary": final_summary,
        "word_count": len(final_summary.split()),
        "source": source
    }

    if verbose:
        print(json.dumps(final_output, indent=2))
    return final_output

def run_pipeline(title: str, content: str, temperature: float = TEMPERATURE, verbose: bool = True) -> dict:
    """Run the full Planner -> Reviewer -> Finalizer pipeline once and return the final output."""
    planner_result = planner_step(title, content, temperature, verbose)
    reviewer_result = reviewer_step(title, content, planner_result, temperature, verbose)
    final_result = finalizer_step(planner_result, reviewer_result, verbose)
    return final_result

def main():
    """
    Main execution.

    Default mode (no arguments): runs the demo pipeline on the fixed example
    Rental Housing listing and prints each stage verbosely, as used for Part 2.

    Test mode: python agents_demo.py <input_json_path> <temperature>
    Loads {"title": ..., "content": ...} from input_json_path, runs the same
    pipeline once at the given temperature, and prints ONLY a single-line JSON
    object {"tags": [...], "summary": ..., "latency_ms": ...} to stdout - used
    by run_nondeterminism_tests.py for the Part 3 non-determinism experiment.
    """
    args = sys.argv[1:]

    if len(args) >= 2:
        # Test mode: quiet, single-line JSON output for automated scripting.
        input_path = args[0]
        temperature = float(args[1])

        with open(input_path, "r") as f:
            input_data = json.load(f)

        start_time = time.time()
        final_result = run_pipeline(
            input_data["title"], input_data["content"], temperature, verbose=False
        )
        latency_ms = (time.time() - start_time) * 1000

        print(json.dumps({
            "tags": final_result["tags"],
            "summary": final_result["summary"],
            "latency_ms": latency_ms
        }))
        return final_result

    # Default demo mode (Part 2): Example input (Rental Housing domain)
    title = "Spacious 2BR Apartment in Downtown San Jose"
    content = """This beautifully renovated 2-bedroom, 1-bathroom apartment is located in the heart of downtown San Jose.
    Features include hardwood floors, high ceilings, in-unit washer/dryer, and a large balcony with city views.
    Building amenities include a fitness center, rooftop garden, and 24/7 security. Near public transit, restaurants,
    and shopping. Pet-friendly with a $500 deposit. Move-in special: first month 50% off. Lease term flexible."""

    print(f"INPUT TITLE: {title}")
    print(f"INPUT CONTENT: {content}")

    final_result = run_pipeline(title, content, TEMPERATURE, verbose=True)

    print("\n" + "="*80)
    print("FINAL PUBLISH OUTPUT (VALID JSON):")
    print("="*80)
    print(json.dumps(final_result, indent=2))

    return final_result

if __name__ == "__main__":
    main()
