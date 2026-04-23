"""
Standalone ADK runner – run the aircraft agent in the terminal.
Usage:  python adk_runner.py
"""

import asyncio
from dotenv import load_dotenv
load_dotenv()

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types
from agent import root_agent

SESSION_ID = "cli-session"
USER_ID    = "user"
APP_NAME   = "aircraft_app"

async def main():
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        agent=root_agent,
        app_name=APP_NAME,
        session_service=session_service,
    )

    print("\n=== Aircraft Intelligence Agent ===")
    print("Type your question (or 'quit' to exit)\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in ("quit", "exit"):
            break

        message = genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_input)],
        )

        print("Agent: ", end="", flush=True)
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=SESSION_ID,
            new_message=message,
        ):
            if event.is_final_response() and event.content:
                for part in event.content.parts:
                    if hasattr(part, "text") and part.text:
                        print(part.text)
        print()


if __name__ == "__main__":
    asyncio.run(main())
