#!/usr/bin/env python3
"""
Part 2: Agentic AI - Planner → Reviewer → Finalizer Flow
Domain: Rental Housing Listings (DOMAIN_ID 6)
Uses Ollama with local LLM to generate tags and summary
"""

import json
import sys
from typing import Optional
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

# Configuration
MODEL_NAME = "qwen2:7b"  # or qwen3:8b if hardware supports
OLLAMA_BASE_URL = "http://localhost:11434"
TEMPERATURE = 0.7

def create_planner_agent() -> ChatOllama:
    """Create the Planner agent."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        format="json"
    )

def create_reviewer_agent() -> ChatOllama:
    """Create the Reviewer agent."""
    return ChatOllama(
        model=MODEL_NAME,
        base_url=OLLAMA_BASE_URL,
        temperature=TEMPERATURE,
        format="json"
    )

def planner_step(title: str, content: str) -> dict:
    """
    Planner Agent: Generates initial tags and summary from title and content.
    Returns a JSON object with tags and summary.
    """
    planner = create_planner_agent()

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
        print("\n" + "="*80)
        print("PLANNER OUTPUT:")
        print("="*80)
        print(json.dumps(result, indent=2))
        return result
    except json.JSONDecodeError:
        print(f"ERROR: Planner output is not valid JSON:\n{response.content}")
        return {"tags": [], "summary": "", "reasoning": "Failed to parse"}

def reviewer_step(title: str, content: str, planner_output: dict) -> dict:
    """
    Reviewer Agent: Reviews and potentially improves the Planner's tags and summary.
    Returns a JSON object indicating changes made.
    """
    reviewer = create_reviewer_agent()

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
        print("\n" + "="*80)
        print("REVIEWER OUTPUT:")
        print("="*80)
        print(json.dumps(result, indent=2))
        return result
    except json.JSONDecodeError:
        print(f"ERROR: Reviewer output is not valid JSON:\n{response.content}")
        return planner_output

def finalizer_step(planner_output: dict, reviewer_output: dict) -> dict:
    """
    Finalizer: Combines Planner and Reviewer outputs into final JSON.
    Ensures exactly 3 tags and ≤25 word summary.
    """
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

    print(json.dumps(final_output, indent=2))
    return final_output

def main():
    """Main execution: Run Planner → Reviewer → Finalizer pipeline."""

    # Example input (Rental Housing domain)
    title = "Spacious 2BR Apartment in Downtown San Jose"
    content = """This beautifully renovated 2-bedroom, 1-bathroom apartment is located in the heart of downtown San Jose.
    Features include hardwood floors, high ceilings, in-unit washer/dryer, and a large balcony with city views.
    Building amenities include a fitness center, rooftop garden, and 24/7 security. Near public transit, restaurants,
    and shopping. Pet-friendly with a $500 deposit. Move-in special: first month 50% off. Lease term flexible."""

    print(f"INPUT TITLE: {title}")
    print(f"INPUT CONTENT: {content}")

    # Step 1: Planner generates initial tags and summary
    planner_result = planner_step(title, content)

    # Step 2: Reviewer reviews and improves if needed
    reviewer_result = reviewer_step(title, content, planner_result)

    # Step 3: Finalizer produces final JSON output
    final_result = finalizer_step(planner_result, reviewer_result)

    # Print final output
    print("\n" + "="*80)
    print("FINAL PUBLISH OUTPUT (VALID JSON):")
    print("="*80)
    print(json.dumps(final_result, indent=2))

    return final_result

if __name__ == "__main__":
    main()
