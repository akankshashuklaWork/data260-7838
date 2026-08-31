#!/usr/bin/env python3
"""
Part 4: Model Client Demo with Token Accounting
Interactive CLI. Type messages to chat; type /stats for token usage stats;
type /exit to quit and see the final cumulative summary.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model_client import ModelClient


def print_separator():
    print("\n" + "=" * 80 + "\n")


def print_stats(client: ModelClient, turn: int):
    """Print token statistics without calling the model or altering history."""
    stats = client.get_stats()
    print(f"\n/stats (after turn {turn}):")
    print(f"  Turn Count: {stats['turn_count']}")
    print(f"  Cumulative Input Tokens: {stats['cumulative_input_tokens']}")
    print(f"  Cumulative Output Tokens: {stats['cumulative_output_tokens']}")
    print(f"  Cumulative Total Tokens: {stats['cumulative_total_tokens']}")
    print(f"  Serialized Conversation History Length: {stats['conversation_history_length']} chars")


def run_conversation():
    print("Part 4: Model Client & Token Accounting")
    print("Type a message and press Enter. Type /stats for stats, /exit to quit.")

    client = ModelClient(model="qwen2:7b")

    system_prompt = (
        "You are a helpful assistant. Keep your responses concise and clear. "
        "Respond to the user's questions directly. Do not add extra explanations unless asked."
    )

    turn_num = 0

    while True:
        user_input = input("\nYou: ").strip()

        if not user_input:
            continue

        if user_input == "/exit":
            break

        if user_input == "/stats":
            print_stats(client, turn_num)
            continue

        turn_num += 1

        print_separator()
        print(f"TURN {turn_num}")
        print_separator()
        print(f"User: {user_input}")

        # Build messages (history + new message)
        messages = [{'role': 'system', 'content': system_prompt}]

        for msg in client.get_history():
            if msg.__class__.__name__ == 'SystemMessage':
                continue
            elif msg.__class__.__name__ == 'HumanMessage':
                messages.append({'role': 'user', 'content': msg.content})
            elif msg.__class__.__name__ == 'AIMessage':
                messages.append({'role': 'assistant', 'content': msg.content})

        messages.append({'role': 'user', 'content': user_input})

        try:
            response = client.complete(messages)
            assistant_response = response['content']

            print(f"\nAssistant: {assistant_response}")

            print(f"\nTurn {turn_num} Token Usage:")
            print(f"  Input Tokens (this turn): {response['input_tokens']}")
            print(f"  Output Tokens (this turn): {response['output_tokens']}")
            print(f"  Total Tokens (this turn): {response['total_tokens']}")

        except Exception as e:
            print(f"ERROR: {e}")
            turn_num -= 1
            continue

    # On exit: cumulative summary
    print_separator()
    print("FINAL SUMMARY")
    print_separator()
    final_stats = client.get_stats()
    print("Conversation complete.")
    print(f"Total Turns: {final_stats['turn_count']}")
    print(f"Total Input Tokens: {final_stats['cumulative_input_tokens']}")
    print(f"Total Output Tokens: {final_stats['cumulative_output_tokens']}")
    print(f"Total Tokens Used: {final_stats['cumulative_total_tokens']}")
    print(f"Serialized Conversation History Length: {final_stats['conversation_history_length']} chars")


if __name__ == "__main__":
    try:
        run_conversation()
    except KeyboardInterrupt:
        print("\n\nConversation interrupted by user.")
        sys.exit(0)
