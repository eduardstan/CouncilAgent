"""CouncilAgent — multi-model LLM with calibrated confidence from inter-agent agreement.

Core pipeline (`run_council`) and agent interface (`CouncilAgent.complete()`) are
both operational. Phases 0-5 complete; see LLMCouncil_Deep_Review.md Part IV.
"""

__version__ = "0.1.0dev0"

from council.agent import CouncilAgent
from council.core import AgentConfig, run_council

__all__ = ["AgentConfig", "CouncilAgent", "run_council"]
