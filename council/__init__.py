"""CouncilAgent — multi-model LLM with calibrated confidence from inter-agent agreement.

Phase 1 builds the core pipeline skeleton. `run_council` will be re-exported here
once Task 1.8 lands. The `CouncilAgent.complete()` user-facing interface is Phase 3.
"""

__version__ = "0.1.0dev0"

from council.core import AgentConfig, run_council

__all__ = ["AgentConfig", "run_council"]
