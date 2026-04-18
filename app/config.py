import os
from dotenv import load_dotenv

load_dotenv()

# Model used for all LLM calls
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Temperature for routing/tool-selection calls (low = deterministic)
OPENAI_TEMPERATURE_ROUTING: float = float(os.getenv("OPENAI_TEMPERATURE_ROUTING", "0.1"))

# Temperature for creative calls (playlist plan, response generation)
OPENAI_TEMPERATURE_CREATIVE: float = float(os.getenv("OPENAI_TEMPERATURE_CREATIVE", "0.7"))
