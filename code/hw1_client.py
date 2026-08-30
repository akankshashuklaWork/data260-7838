#!/usr/bin/env python3
"""
Part 4: Model Client Demo with Token Accounting
5-turn conversation with /stats command
"""

import sys
from src.model_client import ModelClient


def print_separator():
    """Print a visual separator."""
    print("\n" + "=" * 80 + "\n")


def print_stats(client: ModelClient, turn: int):
    """Print token statistics."""
    stats = client.get_stats()
    print(f"\n/stats (After Turn {turn}):")
    print(f"  Turn Count: {stats['turn_count']}")
    print(f"  Cumulative Input Tokens: {stats['cumulative_input_tokens']}")
    print(f"  Cumulative Output Tokens: {stats['cumulative_output_tokens']}")
    print(f"  Cumulative Total Tokens: {stats['cumulative_total_tokens']}")
    print(f"  Conversation History Length: {stats['conversation_history_length']} chars")


def run_conversation():
    """Run a 5-turn conversation with token tracking."""
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "Part 4: Model Client & Token Accounting" + " " * 19 + "║")
    print("║" + " " * 20 + "5-Turn Conversation with /stats" + " " * 27 + "║")
    print("╚" + "=" * 78 + "╝")

    # Initialize client
    client = ModelClient(model="qwen2:7b")

    # System prompt
    system_prompt = """You are a helpful assistant. Keep your responses concise and clear.
Respond to the user's questions directly. Do not add extra explanations unless asked."""

    # Define 5 conversation turns
    turns = [
        {
            "turn": 1,
            "user": "What is machine learning? Explain in 2-3 sentences."
        },
        {
            "turn": 2,
            "user": "Give me 3 real-world examples of machine learning applications."
        },
        {
            "turn": 3,
            "user": "How does supervised learning differ from unsupervised learning?"
        },
        {
            "turn": 4,
            "user": "What is the role of training data in machine learning models?"
        },
        {
            "turn": 5,
            "user": "What are common evaluation metrics for classification models?"
        }
    ]

    # Run turns
    for turn_data in turns:
        turn_num = turn_data['turn']
        user_input = turn_data['user']

        print_separator()
        print(f"TURN {turn_num}")
        print_separator()
        print(f"User: {user_input}")

        # Build messages (history + new message)
        messages = [
            {'role': 'system', 'content': system_prompt}
        ]

        # Add conversation history
        for msg in client.get_history():
            if msg.__class__.__name__ == 'SystemMessage':
                continue  # Skip system messages in history display
            elif msg.__class__.__name__ == 'HumanMessage':
                messages.append({'role': 'user', 'content': msg.content})
            elif msg.__class__.__name__ == 'AIMessage':
                messages.append({'role': 'assistant', 'content': msg.content})

        # Add current user message
        messages.append({'role': 'user', 'content': user_input})

        # Get response from model
        try:
            response = client.complete(messages)
            assistant_response = response['content']

            print(f"\nAssistant: {assistant_response}")

            # Print turn stats
            print(f"\nTurn {turn_num} Token Usage:")
            print(f"  Input Tokens (this turn): {response['input_tokens']}")
            print(f"  Output Tokens (this turn): {response['output_tokens']}")
            print(f"  Total Tokens (this turn): {response['total_tokens']}")

            # Print /stats after turn 3 and turn 5
            if turn_num == 3 or turn_num == 5:
                print_stats(client, turn_num)

        except Exception as e:
            print(f"ERROR: {e}")
            return

    # Final summary
    print_separator()
    print("FINAL SUMMARY")
    print_separator()
    final_stats = client.get_stats()
    print(f"\nConversation Complete!")
    print(f"Total Turns: {final_stats['turn_count']}")
    print(f"Total Input Tokens: {final_stats['cumulative_input_tokens']}")
    print(f"Total Output Tokens: {final_stats['cumulative_output_tokens']}")
    print(f"Total Tokens Used: {final_stats['cumulative_total_tokens']}")
    print(f"Conversation History Size: {final_stats['conversation_history_length']} characters")


if __name__ == "__main__":
    try:
        run_conversation()
    except KeyboardInterrupt:
        print("\n\nConversation interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)
