"""
Model Client Adapter
Reusable wrapper around LLM calls with token accounting
"""

from typing import Optional, List, Dict, Any
from langchain_ollama import ChatOllama
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage


class ModelClient:
    """
    Standardized interface for LLM calls with token tracking.

    All model calls go through this adapter, making it easy to:
    - Switch models
    - Track token usage
    - Maintain conversation history
    - Account for cumulative costs
    """

    def __init__(self, model: str = "qwen2:7b", base_url: str = "http://localhost:11434"):
        """
        Initialize the model client.

        Args:
            model: Model name (default: qwen2:7b)
            base_url: Ollama server URL
        """
        self.model = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=0.7
        )

        # Token tracking
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
        self.turn_count = 0

        # Conversation history
        self.conversation_history: List[BaseMessage] = []

    def complete(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Any]] = None
    ) -> Dict[str, Any]:
        """
        Send messages to the model and get a response.

        Args:
            messages: List of message dicts with 'role' and 'content'
                     Roles: 'system', 'user', 'assistant'
            tools: Optional list of tools (not used in basic implementation)

        Returns:
            Dict with:
            - 'content': LLM response text
            - 'input_tokens': Tokens in this request
            - 'output_tokens': Tokens in this response
            - 'total_tokens': Sum of input + output
        """
        # Convert dict messages to LangChain message objects
        langchain_messages = []
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'system':
                langchain_messages.append(SystemMessage(content=content))
            elif role == 'assistant':
                langchain_messages.append(AIMessage(content=content))
            else:  # user
                langchain_messages.append(HumanMessage(content=content))

        # Call the model
        response = self.model.invoke(langchain_messages)

        # Estimate tokens (Ollama doesn't always return token counts)
        # Simple estimation: ~1 token per 4 characters
        input_tokens = self._estimate_tokens(messages)
        output_tokens = self._estimate_tokens([{'role': 'assistant', 'content': response.content}])
        total_tokens = input_tokens + output_tokens

        # Update cumulative tracking
        self.cumulative_input_tokens += input_tokens
        self.cumulative_output_tokens += output_tokens
        self.turn_count += 1

        # Store in conversation history
        for msg in langchain_messages:
            self.conversation_history.append(msg)
        self.conversation_history.append(AIMessage(content=response.content))

        return {
            'content': response.content,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens,
            'cumulative_input_tokens': self.cumulative_input_tokens,
            'cumulative_output_tokens': self.cumulative_output_tokens,
            'turn_count': self.turn_count
        }

    def add_to_history(self, role: str, content: str) -> None:
        """
        Add a message to conversation history without calling the model.

        Args:
            role: 'system', 'user', or 'assistant'
            content: Message content
        """
        if role == 'system':
            self.conversation_history.append(SystemMessage(content=content))
        elif role == 'assistant':
            self.conversation_history.append(AIMessage(content=content))
        else:
            self.conversation_history.append(HumanMessage(content=content))

    def get_history(self) -> List[BaseMessage]:
        """Get the full conversation history."""
        return self.conversation_history

    def get_history_length(self) -> int:
        """Get the length of conversation history in characters."""
        return sum(len(msg.content) for msg in self.conversation_history)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get current token usage statistics.

        Returns:
            Dict with:
            - turn_count: Number of turns so far
            - cumulative_input_tokens: Total input tokens used
            - cumulative_output_tokens: Total output tokens used
            - cumulative_total_tokens: Total tokens used
            - conversation_history_length: Length in characters
        """
        return {
            'turn_count': self.turn_count,
            'cumulative_input_tokens': self.cumulative_input_tokens,
            'cumulative_output_tokens': self.cumulative_output_tokens,
            'cumulative_total_tokens': self.cumulative_input_tokens + self.cumulative_output_tokens,
            'conversation_history_length': self.get_history_length()
        }

    def reset(self) -> None:
        """Reset conversation history and token tracking."""
        self.conversation_history = []
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
        self.turn_count = 0

    @staticmethod
    def _estimate_tokens(messages: List[Any]) -> int:
        """
        Estimate token count from messages.
        Simple heuristic: ~1 token per 4 characters on average.
        """
        total_chars = 0

        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get('content', '')
            elif isinstance(msg, BaseMessage):
                content = msg.content
            else:
                content = str(msg)

            total_chars += len(content)

        # Rough estimate: 1 token ≈ 4 characters
        return max(1, total_chars // 4)
