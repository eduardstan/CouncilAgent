# LLMCouncil — Deep Architectural Review & Ultimate Plan

**Reviewer**: Claude (Opus 4.6)  
**Date**: April 11, 2026  
**Scope**: Full codebase + plan.md + docs + tests + configs  
**Paradigm shift**: From "council as benchmark" → "council as agent"

---

## Part I — The Vision Gap

Your student has built a *benchmarking harness* for council configurations. That's what `plan.md` specifies, and the code faithfully implements it. But your vision — "treat the council as an agent" — is a fundamentally different and more ambitious thing. It's the difference between building a *test track* for cars and building a *car*.

A **council-as-agent** is a *drop-in replacement* for any single LLM call. Anywhere in any system where you'd write `response = await llm.complete(prompt)`, you should be able to write `response = await council.complete(prompt)` and get a higher-quality, lower-variance answer. The PDF summarization example you gave is perfect: you don't want a benchmark score — you want a *better summary*.

This means the council needs:

1. **The same interface as a single LLM** — `complete(prompt) → response`
2. **Self-contained decision-making** — it figures out *how* to deliberate, not just *that* it should
3. **Cost-awareness** — it operates within a budget, trading off quality for cost
4. **Confidence estimation** — it can tell you *how sure* it is (something a single LLM cannot do reliably)
5. **Task-type awareness** — summarization needs different strategies than math
6. **Composability** — a council member could itself be a council; a council could use tools

The current codebase has *none* of these. It has the lower layers (topology, protocol, aggregation) but not the higher layers that make it an autonomous agent. The benchmarking apparatus is valuable, but it should be the *evaluation* layer of a system whose primary purpose is *production*.

This review is organized in three parts:
- **Part II**: Critical issues in the existing implementation (the things that are wrong)
- **Part III**: Missing abstractions for the council-as-agent paradigm (the things that don't exist yet)
- **Part IV**: The ultimate plan (how to get from here to there)

---

## Part II — Critical Issues in the Existing Implementation

### Issue 1: The Chairman/MetaJudge Duality — A Philosophical Contradiction

**What's happening.** The system has two independent centralizations serving overlapping purposes:

1. `StarTopology` hardcodes `agent_ids[0]` as a "chairman." In even rounds it broadcasts to all peripherals; in odd rounds all peripherals report to it. This agent is structurally privileged — it's the only one that sees all messages.

2. `MetaJudge` aggregation uses a *separate* LLM (hardcoded as `openrouter/openai/gpt-4o-mini`) to read all responses and synthesize a final answer.

These two roles are conceptually identical ("one entity reads everything and produces a synthesis"), but they operate in different layers with different models, and neither knows the other exists. The chairman synthesizes during deliberation; then the MetaJudge re-reads everything flat, discarding the deliberation structure. The chairman's work is wasted.

The default config (`config.yaml`) combines both: `topology: star` + `aggregation: meta_judge` — the most dictatorial possible combination. This directly contradicts:
- Arrow's theorem (which plan.md cites): any single-dictator aggregation violates fairness axioms
- The "Debate or Vote" finding (which plan.md cites): simple majority voting captures most gains
- The project's own ADR 2: topology, protocol, and aggregation should be *independent* concerns

**Why it matters for council-as-agent.** If the council is an agent, it can't have two competing decision-makers inside it. That's like a company where the COO makes all executive decisions, but then a "meta-CEO" re-reads all the memos and makes *different* decisions. The council needs a single, clean decision path.

**Solution analysis.**

*Option A — Remove the chairman, keep MetaJudge:* Star topology becomes a relay pattern (hub routes messages between peripherals but doesn't generate content). MetaJudge is the single synthesis point. **Pros**: Clean separation; topology controls routing, aggregation controls decision-making. **Cons**: Loses the iterative synthesis capability where a chairman refines understanding across rounds.

*Option B — Merge chairman into MetaJudge:* The chairman *is* the MetaJudge — it receives structured deliberation and produces the final answer as part of the star topology's final round. **Pros**: No redundancy; deliberation context is preserved into synthesis. **Cons**: Couples aggregation to topology, breaking ADR 2's independence principle.

*Option C — Topological roles without privileged agents:* Redefine "topology" to mean *only* the communication graph, with no semantic role attached. Star becomes "all messages route through a central point" — but the central point is infrastructure, not an agent. Separately, introduce a `SynthesisStrategy` that can be "none" (vote), "delegate" (one model synthesizes), or "collaborative" (models co-write). This decouples communication structure from decision authority.

**Recommended: Option C.** It resolves the contradiction at the conceptual level, not just the implementation level. The star topology becomes useful for what it genuinely models — hub-and-spoke *latency* patterns — rather than smuggling in a privileged agent. The synthesis strategy becomes an explicit, configurable concern.

**Addendum (discovered during pipeline testing):** When MetaJudge is the aggregator, it must receive the full deliberation history — not just final-round responses. This is the "Area Chair reads the reviews" model: the chair traces how opinions evolved through critique and revision rounds, identifies which arguments were compelling, and produces an informed synthesis. See Issue 11 for the two-paradigm (blind vs informed) aggregation design.

```python
# Revised topology — pure communication graph, no privileged agents
class StarTopology(Topology):
    """Hub-and-spoke routing. The hub is infrastructure, not an agent.
    All peripherals effectively see all other peripherals' messages
    (relayed through the hub), but with 2-hop latency."""
    
    def get_adjacency_matrix(self, round_index: int) -> List[List[bool]]:
        # Every agent sees every other agent (hub is transparent relay)
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]
    
    def get_latency_hops(self, sender_idx: int, receiver_idx: int) -> int:
        """Star topology has 2-hop latency for all pairs."""
        return 2 if sender_idx != receiver_idx else 0

# Revised aggregation — MetaJudge is configurable and structured
class MetaJudge(Aggregation):
    def __init__(self, model: str, structured_input: bool = True):
        self.model = model
        self.structured_input = structured_input
```

---

### Issue 2: The Topology–Protocol Coupling Is Broken Bidirectionally

**What's happening.** ADR 2 claims strict separation: topology controls *who sees whom*, protocol controls *what they say*. In practice, this contract is violated in both directions:

**Direction 1: Protocol ignores topology.** `PeerReviewProtocol.build_prompts()` filters by `r.agent_id != agent_id` (show all others), regardless of what the topology's adjacency matrix says. The pipeline's `_node_deliberation` *does* pre-filter using the adjacency matrix before calling the protocol, but the protocol has no awareness it received a subset. It could just as easily call `state["round_history"]` and bypass the filter entirely.

**Direction 2: Topology encodes protocol semantics.** `StarTopology` alternates between "fan-out" and "funnel" rounds — but that's a *protocol* decision (when to broadcast vs. collect), not a *topology* decision (who can talk to whom). The communication graph shouldn't change based on round parity; that's the protocol deciding that "in odd rounds, only the chairman should speak."

**Why it matters for council-as-agent.** If you want to add a new topology (say, "small-world network"), you shouldn't need to think about round-parity semantics. And if you want a new protocol (say, "Socratic questioning"), it should work with *any* topology without knowing the adjacency matrix internals.

**Solution analysis.**

*Option A — Protocol receives topology:* Pass the adjacency matrix to `build_prompts()` so the protocol can decide what to show based on who's connected. **Pros**: Protocol has full information. **Cons**: Protocol now has two jobs (prompt construction + visibility filtering), defeating the separation.

*Option B — Pipeline enforces contract:* The pipeline is the *only* component that reads the adjacency matrix. It pre-filters responses into a `VisibilityContext` and passes it to the protocol. The protocol *must* use only what it receives. **Pros**: Clean contract. **Cons**: Protocol can't adapt its prompt to partial vs. full visibility.

*Option C — Explicit VisibilityContext with metadata:* The pipeline constructs a rich context object that tells the protocol: "You are agent X. You can see responses from [A, B] out of 5 total agents. This is round 3 of a debate." The protocol uses this to construct appropriate prompts. The topology's *only* job is to produce the adjacency matrix; the pipeline translates it into visibility contexts.

**Recommended: Option C.** It makes the implicit contract explicit, gives protocols enough metadata to write intelligent prompts, and keeps topology as a pure graph concern.

```python
@dataclass
class VisibilityContext:
    """Everything a protocol needs to build a prompt for one agent."""
    agent_id: str
    round_index: int
    visible_responses: List[AgentResponse]    # already filtered by topology
    own_previous_responses: List[AgentResponse]  # agent's own history
    total_agents: int                          # for "you see 2 of 5" prompts
    communication_mode: str                    # "individual" | "broadcast" | "relay"
    original_prompt: str

class Protocol(abc.ABC):
    @abc.abstractmethod
    def build_prompt(self, ctx: VisibilityContext) -> str:
        """Build the prompt for a single agent given its visibility context.
        
        The protocol MUST use only ctx.visible_responses — it does not
        have access to the full history. The topology controls visibility;
        the protocol controls presentation.
        """
        ...
```

The key insight: **the topology is now completely decoupled.** `StarTopology` no longer needs round-parity logic. It's a static graph. If you want round-dependent visibility, that's a `DynamicTopology` subclass — but the dynamics are about the *graph structure*, not about protocol semantics.

```python
class StarTopology(Topology):
    """Static hub-and-spoke. All agents see all others (relayed through hub)."""
    def get_adjacency_matrix(self, round_index: int) -> List[List[bool]]:
        n = self.num_agents
        return [[i != j for j in range(n)] for i in range(n)]

class DynamicStarTopology(Topology):
    """Alternating fan-out/fan-in star. Round-dependent visibility."""
    def get_adjacency_matrix(self, round_index: int) -> List[List[bool]]:
        matrix = [[False]*self.num_agents for _ in range(self.num_agents)]
        if round_index % 2 == 0:  # fan-out: hub broadcasts
            for i in range(1, self.num_agents):
                matrix[0][i] = True
        else:  # fan-in: peripherals report
            for i in range(1, self.num_agents):
                matrix[i][0] = True
        return matrix
```

---

### Issue 3: MajorityVote on Free-Text Is Meaningless

**What's happening.** `MajorityVote` uses `Counter(r.content.strip())` — exact string matching on raw LLM output. Since LLMs never produce byte-identical responses for the same answer, every count is 1 and the "majority" winner is arbitrary.

This is not just a `MajorityVote` bug — it invalidates *every baseline* in the benchmark. `self_consistency` uses `MajorityVote`. `random_vote` uses `MajorityVote`. Both are measuring noise, not signal.

**Why it matters for council-as-agent.** The PDF summarization example: three LLMs summarize the same PDF. Their summaries will use different words, sentence structures, emphases. Exact string matching will always say "no agreement," even if all three summaries convey the same information. The council needs a concept of *semantic equivalence*, not string equality.

**Solution analysis.**

*Option A — Prompt engineering for structured output:* Force all council members to produce a structured answer (JSON with specific fields), then compare structured fields. For math: `{"answer": 72}`. For summarization: `{"key_points": [...], "conclusion": "..."}`. **Pros**: Deterministic, fast, no extra model calls. **Cons**: Loses nuance; summarization quality can't be reduced to key-point matching.

*Option B — Embedding-based clustering:* Embed all responses, cluster by cosine similarity, pick the largest cluster's centroid. **Pros**: Works for any response type. **Cons**: Expensive (embedding model), introduces threshold hyperparameter, centroid selection is lossy.

*Option C — Task-type-aware answer extraction pipeline:* Introduce an `AnswerNormalizer` abstraction that's configured per task type. For objective tasks (math, factual QA), it extracts and normalizes the answer. For subjective tasks (summarization, creative writing), it delegates to semantic comparison or to the MetaJudge. The normalizer sits *between* deliberation and aggregation.

**Recommended: Option A for benchmarking, Option C for production.** For the thesis/benchmark, structured output is the right call — it's deterministic, reproducible, and easy to validate. For the council-as-agent production system, the full `AnswerNormalizer` pipeline gives you task-type awareness.

Both approaches benefit from this abstraction:

```python
class AnswerNormalizer(abc.ABC):
    """Extracts and normalizes the 'answer' from a raw LLM response."""
    @abc.abstractmethod
    async def normalize(self, response: str) -> str: ...

class StructuredOutputNormalizer(AnswerNormalizer):
    """Parses JSON structured output from LLMs."""
    def __init__(self, answer_field: str = "answer"):
        self.answer_field = answer_field
    
    async def normalize(self, response: str) -> str:
        try:
            data = json.loads(response)
            return str(data.get(self.answer_field, response)).strip().lower()
        except json.JSONDecodeError:
            # Fallback: regex extraction
            for pattern in [
                r'"answer"\s*:\s*"?([^",}]+)',
                r'(?:answer|result)\s*(?:is|=|:)\s*(.+?)(?:\.|$)',
                r'(\-?\d+(?:\.\d+)?)\s*$',
            ]:
                m = re.search(pattern, response, re.IGNORECASE | re.MULTILINE)
                if m:
                    return m.group(1).strip().lower()
            return response.strip().lower()

class SemanticNormalizer(AnswerNormalizer):
    """Groups semantically equivalent responses."""
    def __init__(self, model, threshold: float = 0.85):
        self.model = model
        self.threshold = threshold
    
    async def normalize(self, response: str) -> str:
        # Returns the response as-is; clustering happens at aggregation level
        return response

# Wire into MajorityVote
class MajorityVote(Aggregation):
    def __init__(self, normalizer: Optional[AnswerNormalizer] = None):
        self.normalizer = normalizer or StructuredOutputNormalizer()
    
    async def aggregate(self, responses, **kwargs):
        normalized = [await self.normalizer.normalize(r.content) for r in responses]
        counts = Counter(normalized)
        winner_key, freq = counts.most_common(1)[0]
        
        # Return the original (un-normalized) response that matches
        for r, norm in zip(responses, normalized):
            if norm == winner_key:
                return AggregationResult(
                    final_answer=r.content,
                    confidence=freq / len(responses),
                    method="MajorityVote",
                    metadata={"normalized_counts": dict(counts)}
                )
```

The structured output approach also solves **Issue 4** (regex ranking extraction) — if all models output JSON, you parse JSON instead of regex. One solution, two issues fixed.

---

### Issue 4: Ranking Extraction via Regex — Solved by Structured Output

**What's happening.** `RegexOrdinalRanking` expects `"FINAL RANKING: A > B > C"`. LLMs rarely produce this exact format. When regex fails, the ranking is empty, and `BordaCount` crashes or gives zero points.

**Why it matters.** Every aggregation method that depends on rankings (Borda, Weighted, Pairwise) is only as good as the ranking extraction. If extraction fails 30% of the time, 30% of your benchmark data points are garbage.

**The solution is structural, not more regex.** If you enforce structured output at the protocol level (via LiteLLM's `response_format` or function calling), the ranking parser becomes `json.loads()`:

```python
class StructuredRanking(Ranking):
    """Parses rankings from JSON structured output."""
    
    # This schema is injected into the protocol's prompt
    SCHEMA = {
        "type": "object",
        "properties": {
            "ranking": {
                "type": "array", "items": {"type": "string"},
                "description": "Response labels ordered from best to worst"
            },
            "scores": {
                "type": "object", 
                "additionalProperties": {"type": "number"},
                "description": "Score (1-10) for each response label"
            },
            "reasoning": {"type": "string"}
        },
        "required": ["ranking", "scores"]
    }
    
    def extract(self, text: str, agent_ids: List[str]) -> PreferenceData:
        try:
            data = json.loads(text)
            ordered = [aid for aid in data["ranking"] if aid in agent_ids]
            scores = {k: v for k, v in data.get("scores", {}).items() if k in agent_ids}
            
            # Return BOTH ordinal and cardinal — let the aggregation pick
            return RichPreference(
                raw_text=text,
                ordered_ids=ordered,
                scores=scores,
                reasoning=data.get("reasoning", "")
            )
        except (json.JSONDecodeError, KeyError):
            # Graceful fallback to regex
            return RegexOrdinalRanking().extract(text, agent_ids)

@dataclass
class RichPreference(PreferenceData):
    """Unified preference data containing both ordinal and cardinal information."""
    ordered_ids: List[str] = field(default_factory=list)
    scores: Dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
```

The key design decision: **protocols should inject the response schema into their prompts**. The protocol knows what kind of output the downstream ranking/aggregation expects. This is not a leaky abstraction — it's the protocol's job to instruct agents on how to respond.

```python
class PeerReviewProtocol(Protocol):
    def __init__(self, anonymize: bool = True, output_schema: Optional[dict] = None):
        self.anonymize = anonymize
        self.output_schema = output_schema
    
    def build_prompt(self, ctx: VisibilityContext) -> str:
        prompt = self._build_review_prompt(ctx)
        
        if self.output_schema:
            prompt += f"\n\nRespond ONLY with valid JSON matching this schema:\n"
            prompt += json.dumps(self.output_schema, indent=2)
        
        return prompt
```

---

### Issue 5: BusTopology ≡ CompleteGraphTopology (Semantic Vacuity)

**What's happening.** Identical code, different class names. `plan.md` distinguishes them conceptually (bus = shared memory, complete = pairwise messaging), but the implementation makes no distinction.

**The real issue is deeper.** The taxonomy identifies "communication mode" as a design dimension, but the `Topology` abstraction only models *who can send to whom* (adjacency matrix). It doesn't model *how* the communication happens — shared memory vs. direct messaging vs. relay. These modes produce different prompt structures even with identical visibility:

- **Bus/Broadcast**: "Here is the shared discussion board. All participants have contributed. Review the board and add your thoughts." (One flat document, agents feel like they're contributing to a wiki.)
- **Complete/Individual**: "Here is what Response A said: [...]. Here is what Response B said: [...]." (Labeled individual messages, agents feel like they're in a conversation.)
- **Relay**: "Here is the message passed to you from the previous participant: [...]." (Sequential chain, agents feel like they're refining a draft.)

Same adjacency matrix. Completely different agent behavior.

**Solution.** Encode communication mode in the `VisibilityContext`:

```python
class CommunicationMode(str, Enum):
    INDIVIDUAL = "individual"   # Separate labeled messages per agent
    BROADCAST = "broadcast"     # Single shared document / board
    RELAY = "relay"             # Sequential pass-through

# Bus sets mode=BROADCAST, Complete sets mode=INDIVIDUAL
class BusTopology(Topology):
    communication_mode = CommunicationMode.BROADCAST
    # adjacency is complete graph

class CompleteGraphTopology(Topology):
    communication_mode = CommunicationMode.INDIVIDUAL
    # adjacency is complete graph

class RingTopology(Topology):
    communication_mode = CommunicationMode.RELAY
    # adjacency is ring
```

The protocol then uses the mode to format prompts differently:

```python
def _format_responses(self, ctx: VisibilityContext) -> str:
    labeled = anonymize_responses(ctx.visible_responses, ctx.agent_id, self.anonymize)
    
    if ctx.communication_mode == CommunicationMode.BROADCAST:
        return "=== Shared Discussion Board ===\n" + "\n---\n".join(
            f"{label}: {r.content}" for label, r in labeled
        )
    elif ctx.communication_mode == CommunicationMode.RELAY:
        # Only show the most recent relay
        if labeled:
            label, r = labeled[-1]
            return f"The previous participant wrote:\n{r.content}"
        return ""
    else:  # INDIVIDUAL
        return "\n\n".join(
            f"### {label}\n{r.content}" for label, r in labeled
        )
```

Now Bus and Complete have genuinely different behavior despite identical adjacency matrices.

---

### Issue 6: Anonymization Is Inconsistent

**What's happening.** `PeerReviewProtocol` anonymizes (`"Response A"`, `"Response B"`). `DebateProtocol` leaks agent IDs (`"Model claude_haiku"`). `SimultaneousProtocol` also leaks (`"Model {resp.agent_id}"`). Anonymization is the stated default (`anonymize: true` in config), but only one protocol implements it.

**Solution.** Centralize anonymization in the `VisibilityContext` construction, not in each protocol:

```python
# In pipeline, when building VisibilityContext:
def _build_visibility_context(self, agent_id, round_index, visible_responses):
    if self.anonymize:
        # Create anonymized copies of responses
        labeled = []
        for i, r in enumerate(visible_responses):
            anon_r = AgentResponse(
                agent_id=f"Response {chr(65 + i)}",  # A, B, C...
                content=r.content,
                round_index=r.round_index,
                metadata={**(r.metadata or {}), "_real_agent_id": r.agent_id}
            )
            labeled.append(anon_r)
        visible_responses = labeled
    
    return VisibilityContext(
        agent_id=agent_id if not self.anonymize else f"You",
        visible_responses=visible_responses,
        ...
    )
```

Now *every* protocol automatically gets anonymized inputs. No protocol needs to implement anonymization logic. The real agent IDs are preserved in metadata for post-hoc analysis.

---

### Issue 7: SimultaneousProtocol Has Quadratic Context Growth

**What's happening.** `SimultaneousProtocol` includes ALL responses from ALL previous rounds. With N agents and R rounds, context size grows as O(N × R). Five agents over 5 rounds = 25 full responses in the prompt.

**Why it matters for council-as-agent.** In production, councils might run for many rounds on complex tasks. Quadratic context growth means either hitting context window limits or spending enormous amounts on tokens.

**Solution analysis.**

*Option A — Sliding window:* Only include the last K rounds. **Pros**: Simple, bounded. **Cons**: Agents lose context from early rounds.

*Option B — Progressive summarization:* Summarize older rounds into condensed paragraphs, keep recent rounds in full. **Pros**: Preserves information in compressed form. **Cons**: Adds summarization calls (cost), introduces information loss.

*Option C — Hierarchical context management:* Maintain a "council memory" that's progressively refined. Each round, a lightweight summarizer compresses the previous round into a "state of the discussion" document. Agents see: (1) the original prompt, (2) the current state-of-discussion, (3) the most recent round's full responses.

**Recommended: Option C for production, Option A for benchmarking.**

```python
class SimultaneousProtocol(Protocol):
    def __init__(self, context_strategy: str = "full", window_size: int = 2):
        self.context_strategy = context_strategy  # "full" | "window" | "summarized"
        self.window_size = window_size
    
    def build_prompt(self, ctx: VisibilityContext) -> str:
        prompt = f"Original Task: {ctx.original_prompt}\n\n"
        
        if self.context_strategy == "full":
            # Current behavior — all history
            prompt += self._format_all_responses(ctx)
        
        elif self.context_strategy == "window":
            # Only recent rounds
            recent = [r for r in ctx.visible_responses 
                      if r.round_index >= ctx.round_index - self.window_size]
            older_count = len(ctx.visible_responses) - len(recent)
            if older_count > 0:
                prompt += f"[{older_count} earlier responses omitted for brevity]\n\n"
            prompt += self._format_responses(recent, ctx)
        
        elif self.context_strategy == "summarized":
            # Requires council_memory in context
            if ctx.council_memory:
                prompt += f"## State of Discussion\n{ctx.council_memory}\n\n"
            prompt += "## Latest Round\n"
            latest = [r for r in ctx.visible_responses 
                      if r.round_index == ctx.round_index - 1]
            prompt += self._format_responses(latest, ctx)
        
        prompt += "\nBased on the above, provide your updated response."
        return prompt
```

---

### Issue 8: PeerReview Is Single-Round — A Half-Built Protocol

**What's happening.** `PeerReviewProtocol` handles generation (round 0) and critique (round 1). If `max_rounds > 1`, rounds 2+ repeat the same critique prompt with stale round-0 responses. The `pending_refinements.md` flags this.

**Solution.** Implement the alternating critique-revision cycle. The key insight: **review and revision are symmetric opposites.** In odd rounds, agents critique. In even rounds, agents revise based on critiques. This maps naturally to the academic peer review process: submit → review → revise → re-review.

**Critical corollary: answer rounds vs. deliberation rounds.** The protocol produces two distinct types of output — *answers* (round 0, 2, 4…) and *critiques* (round 1, 3, 5…). The core pipeline must know which is which, because only answer-round responses should be fed to ranking and aggregation. Critique text is deliberation artefact, not a candidate answer. The protocol should declare this via `is_answer_round(round_index: int) -> bool`. Feeding critique text to `MajorityVote` produces nonsensical results (every critique is a unique string → confidence ≈ 1/N). Structured JSON output (`response_format`) should only be enforced on answer rounds; critique rounds should remain free text.

```python
class PeerReviewProtocol(Protocol):
    def __init__(self, anonymize: bool = True, output_schema: Optional[dict] = None):
        self.anonymize = anonymize
        self.output_schema = output_schema
    
    def build_prompt(self, ctx: VisibilityContext) -> str:
        if ctx.round_index == 0:
            return ctx.original_prompt
        
        is_critique = ctx.round_index % 2 == 1
        prev_responses = [r for r in ctx.visible_responses 
                          if r.round_index == ctx.round_index - 1]
        labeled = anonymize_responses(prev_responses, ctx.agent_id, self.anonymize)
        
        if is_critique:
            return self._build_critique_prompt(ctx, labeled)
        else:
            return self._build_revision_prompt(ctx, labeled)
    
    def _build_critique_prompt(self, ctx, labeled_responses):
        responses_text = "\n\n".join(
            f"### {label}\n{r.content}" for label, r in labeled_responses
        )
        prompt = (
            f"Original Task: {ctx.original_prompt}\n\n"
            f"Review these {'revised ' if ctx.round_index > 1 else ''}responses:\n\n"
            f"{responses_text}\n\n"
            "Provide constructive critique. Identify strengths, weaknesses, "
            "factual errors, and areas for improvement in each response. "
            "Be specific and actionable."
        )
        if self.output_schema:
            prompt += f"\n\nRespond in JSON: {json.dumps(self.output_schema)}"
        return prompt
    
    def _build_revision_prompt(self, ctx, labeled_critiques):
        # Find this agent's own most recent response
        own_responses = sorted(ctx.own_previous_responses, 
                               key=lambda r: r.round_index, reverse=True)
        own_text = own_responses[0].content if own_responses else "[not available]"
        
        critiques_text = "\n\n".join(
            f"### Feedback from {label}\n{r.content}" for label, r in labeled_critiques
        )
        return (
            f"Original Task: {ctx.original_prompt}\n\n"
            f"Your previous response:\n{own_text}\n\n"
            f"Feedback received:\n\n{critiques_text}\n\n"
            "Revise your response based on this feedback. Address the criticisms, "
            "fix any errors identified, and improve your answer. "
            "Maintain your position where the criticism is unfounded."
        )
```

---

### Issue 9: `task_accuracy` Fuzzy Match Produces False Positives

**What's happening.** `return 1.0 if g in p else 0.0` — substring match. "72" matches "172", "5" matches "235", "10" matches "100". This is the default evaluation method used throughout `run.py`.

**Solution.** Use word-boundary matching as the primary method, with numerical extraction as the first pass:

```python
async def task_accuracy(predicted: str, ground_truth: str, 
                        method: str = "smart") -> float:
    p, g = predicted.strip(), ground_truth.strip()
    
    if method == "smart":
        # 1. Numerical comparison (handles "72", "72.0", etc.)
        g_nums = re.findall(r'-?\d+(?:,\d{3})*(?:\.\d+)?', g)
        if g_nums:
            g_val = float(g_nums[-1].replace(',', ''))
            p_nums = re.findall(r'-?\d+(?:,\d{3})*(?:\.\d+)?', p)
            for pn in p_nums:
                try:
                    if abs(float(pn.replace(',', '')) - g_val) < 1e-6:
                        return 1.0
                except ValueError:
                    continue
        
        # 2. Word-boundary match (prevents "5" matching "15")
        escaped = re.escape(g.lower())
        if re.search(rf'\b{escaped}\b', p.lower()):
            return 1.0
        
        return 0.0
    
    elif method == "exact":
        return 1.0 if p.lower() == g.lower() else 0.0
    
    elif method == "llm_judge":
        # ... existing LLM judge logic ...
        pass
```

---

### Issue 10: No Adaptive Termination

**What's happening.** All deliberation runs for a fixed `max_rounds`. No consensus detection, no early stopping, no cost-based cutoff. The plan.md specifies a `ConsensusDetector` and hypothesis H10 (KL-divergence adaptive termination). Neither exists.

**Why it matters for council-as-agent.** In production, you can't afford to run 5 rounds of deliberation for every query. Most queries don't need deliberation at all. The council must decide *when to stop* based on how much the agents agree.

**Solution.** Pluggable termination strategies:

```python
class TerminationStrategy(abc.ABC):
    @abc.abstractmethod
    def should_terminate(self, state: CouncilState) -> Tuple[bool, str]:
        """Returns (should_stop, reason)."""
        ...

class FixedRounds(TerminationStrategy):
    def __init__(self, max_rounds: int):
        self.max_rounds = max_rounds
    def should_terminate(self, state):
        done = state["current_round"] >= self.max_rounds
        return done, f"Reached max rounds ({self.max_rounds})"

class AgreementThreshold(TerminationStrategy):
    """Stop when agents sufficiently agree."""
    def __init__(self, threshold: float = 0.8, min_rounds: int = 1, 
                 max_rounds: int = 10, normalizer: Optional[AnswerNormalizer] = None):
        self.threshold = threshold
        self.min_rounds = min_rounds
        self.max_rounds = max_rounds
        self.normalizer = normalizer or StructuredOutputNormalizer()
    
    async def should_terminate(self, state):
        r = state["current_round"]
        if r < self.min_rounds:
            return False, "Below minimum rounds"
        if r >= self.max_rounds:
            return True, f"Reached max rounds ({self.max_rounds})"
        
        latest = [resp for resp in state["round_history"] 
                  if resp.round_index == r]
        if len(latest) < 2:
            return True, "Insufficient responses"
        
        normalized = [await self.normalizer.normalize(resp.content) for resp in latest]
        counts = Counter(normalized)
        agreement = counts.most_common(1)[0][1] / len(normalized)
        
        if agreement >= self.threshold:
            return True, f"Agreement {agreement:.0%} >= threshold {self.threshold:.0%}"
        return False, f"Agreement {agreement:.0%} < threshold {self.threshold:.0%}"

class BudgetExhaustion(TerminationStrategy):
    """Stop when cost budget is exhausted."""
    def __init__(self, max_cost: float, max_rounds: int = 20):
        self.max_cost = max_cost
        self.max_rounds = max_rounds
    
    def should_terminate(self, state):
        if state["current_round"] >= self.max_rounds:
            return True, "Max rounds"
        if state["total_cost"] >= self.max_cost:
            return True, f"Budget exhausted (${state['total_cost']:.4f} >= ${self.max_cost:.4f})"
        return False, f"Budget remaining: ${self.max_cost - state['total_cost']:.4f}"

class CompositeTermination(TerminationStrategy):
    """Combines multiple strategies with OR logic (stop if any says stop)."""
    def __init__(self, strategies: List[TerminationStrategy]):
        self.strategies = strategies
    
    async def should_terminate(self, state):
        for s in self.strategies:
            result = s.should_terminate(state)
            if asyncio.iscoroutine(result):
                result = await result
            done, reason = result
            if done:
                return True, reason
        return False, "No termination condition met"
```

**Semantic clarification: `max_rounds` in config means deliberation cycles, not raw rounds.** The `FixedRounds` termination strategy operates on raw round counts internally, but experiment configs expose `max_rounds` as the number of deliberation cycles *after* initial generation. The runner translates: `total_raw_rounds = 1 + max_rounds * protocol.cycle_length()`. For PeerReview (cycle_length=2), `max_rounds: 1` → 3 raw rounds (generate, critique, revise). For Direct/Simultaneous (cycle_length=1), `max_rounds: 1` → 2 raw rounds. `max_rounds: 0` always means generate-only regardless of protocol. This keeps the config semantic stable across protocol changes — switching from PeerReview to Simultaneous doesn't silently halve the deliberation depth.

---

### Issue 11: MetaJudge Gets Unstructured Flat Input — And Misses the Debate Arc

Already detailed in the previous analysis. The fix is round-structured prompts with phase labels. Combined with structured output enforcement (Issue 4), the MetaJudge becomes dramatically more reliable.

**Deeper issue discovered during pipeline testing.** There are two fundamentally different aggregation paradigms, and the current code conflates them:

1. **Blind aggregation** (MajorityVote, BordaCount, Condorcet): counts normalized final-round answers. Does not need — and should not receive — the deliberation history. These methods are fast, statistically grounded, and immune to narrative manipulation.

2. **Informed aggregation** (MetaJudge): an LLM reads the *full debate arc* — initial answers, critiques, revisions, preference signals — and synthesizes a final answer. This is the "Area Chair" model from academic peer review: the chair doesn't just count reviewer scores, they *read the discussion* to understand *why* opinions shifted, who made compelling arguments, and whether critiques were addressed.

Currently, MetaJudge receives only the final-round responses as a flat list. This discards the entire deliberation history — the very thing that makes multi-round councils valuable. An informed aggregator that can't see the debate is like an area chair who only reads the final scores without reading the reviews.

**Fix.** `Aggregation.aggregate()` receives an optional `round_history: list[AgentResponse]` parameter. Blind aggregators ignore it. `MetaJudge` uses it to construct a structured prompt showing the full deliberation arc with phase labels (GENERATE, CRITIQUE, REVISION) so the synthesis model can trace how consensus formed or where disagreement persists. This does not violate Constitution §3 — aggregation still controls the decision; it just has access to richer input.

---

### Issue 12: State Accumulation Race Conditions

Token counts use `state.get("tokens_in", 0) + tokens_in` instead of LangGraph's reducer pattern. If LangGraph ever runs nodes concurrently, counts are lost. Use `Annotated[int, operator.add]` for all numerical accumulators.

---

### Issue 13: No Condorcet or Advanced Social Choice Methods

`plan.md` discusses Arrow's theorem, Condorcet winners, and strategy-proofness at length. Only Borda Count is implemented. Adding Condorcet + Copeland's fallback is straightforward given the `PairwiseComparison` ranking extractor:

```python
class CondorcetAggregation(Aggregation):
    """Condorcet winner if one exists, Copeland's method as fallback."""
    async def aggregate(self, responses, preferences=None, **kwargs):
        win_matrix = self._build_win_matrix(preferences)
        
        # Check for Condorcet winner (beats everyone in pairwise)
        for candidate in win_matrix:
            if all(win_matrix[candidate][opp] > win_matrix[opp][candidate] 
                   for opp in win_matrix if opp != candidate):
                return self._make_result(candidate, "Condorcet", responses)
        
        # Copeland fallback (most net pairwise wins)
        scores = {a: sum(1 if win_matrix[a][b] > win_matrix[b][a] else -1 
                         for b in win_matrix if b != a) for a in win_matrix}
        winner = max(scores, key=scores.get)
        return self._make_result(winner, "Copeland", responses, {"scores": scores})
```

---

## Part III — Missing Abstractions for Council-as-Agent

These aren't bugs in the existing code — they're *entire layers* that need to exist for the council to function as a production agent.

### Missing Abstraction 1: The Unified Agent Interface

**The problem.** The `Council` class returns a `CouncilState` dictionary with `round_history`, `preferences`, `final_result`, etc. This is fine for a benchmark but useless as a drop-in LLM replacement. You can't pass a `Council` to any existing tool or framework that expects an LLM.

**What's needed.** A `CouncilAgent` wrapper that implements the standard LLM interface:

```python
class CouncilAgent:
    """Drop-in replacement for a single LLM. Same interface, higher quality."""
    
    def __init__(self, config: CouncilConfig):
        self.council = Council.from_config(config)
    
    async def complete(self, prompt: str, **kwargs) -> ModelResponse:
        """Same signature as ModelClient.complete().
        Returns a single response — the council's synthesized answer."""
        state = await self.council.arun(prompt)
        result = state["final_result"]
        
        return ModelResponse(
            content=result.final_answer,
            model=f"council:{self.council.config_name}",
            tokens_in=state["tokens_in"],
            tokens_out=state["tokens_out"],
            latency_ms=state.get("wall_clock_ms", 0),
            cost=state["total_cost"],
            cached=False,
            metadata={
                "confidence": result.confidence,
                "agreement_ratio": self._compute_agreement(state),
                "rounds_used": state["current_round"],
                "method": result.method,
            }
        )
    
    def _compute_agreement(self, state) -> float:
        """The council's unique advantage: it can estimate its own confidence
        from inter-agent agreement. A single LLM cannot do this."""
        latest = [r for r in state["round_history"] 
                  if r.round_index == state["current_round"]]
        if len(latest) < 2:
            return 1.0
        # ... normalize and compute agreement ratio ...
```

This is the *bridge* between the benchmarking world and the production world. The same `Council` object powers both use cases — the benchmark calls `council.arun()` to inspect internals, and production calls `council_agent.complete()` for a clean interface.

**The key insight.** The `metadata.confidence` field is something only a council can provide. A single LLM's self-reported confidence is unreliable (models are poorly calibrated). A council's inter-agent agreement is an *empirical* confidence signal — if 5 independent models agree, you can be more confident than if they disagree. This is the council's unique value proposition beyond accuracy.

---

### Missing Abstraction 2: Task-Type Awareness

**The problem.** The same council pipeline runs for GSM8K math problems and (hypothetically) PDF summarization. But these tasks need radically different strategies:

| Dimension | Math/Factual | Summarization | Creative Writing |
|-----------|-------------|---------------|-----------------|
| Answer equivalence | Exact numerical match | Semantic similarity | Subjective preference |
| Best aggregation | Majority vote | MetaJudge synthesis | Best-of-N selection |
| Value of deliberation | Low (vote is enough) | High (diverse perspectives enrich) | Medium (critique helps, but don't average creativity) |
| Structured output | `{"answer": 72}` | `{"summary": "...", "key_points": [...]}` | Free text |
| Confidence signal | Agreement ratio | Coverage overlap | Subjective scoring |

**What's needed.** A `TaskProfile` that drives council configuration:

```python
@dataclass
class TaskProfile:
    """Describes the properties of a task class.
    The council uses this to auto-configure its strategy."""
    
    name: str
    answer_type: str            # "exact" | "semantic" | "subjective"
    normalizer: AnswerNormalizer
    recommended_aggregation: str  # "vote" | "synthesis" | "selection"
    deliberation_value: str       # "low" | "medium" | "high"
    output_schema: Optional[dict] = None  # JSON schema for structured output
    
    @classmethod
    def math(cls) -> "TaskProfile":
        return cls(
            name="math",
            answer_type="exact",
            normalizer=StructuredOutputNormalizer(answer_field="answer"),
            recommended_aggregation="vote",
            deliberation_value="low",
            output_schema={"type": "object", "properties": {
                "reasoning": {"type": "string"},
                "answer": {"type": "number"}
            }, "required": ["answer"]}
        )
    
    @classmethod
    def summarization(cls) -> "TaskProfile":
        return cls(
            name="summarization",
            answer_type="semantic",
            normalizer=SemanticNormalizer(),
            recommended_aggregation="synthesis",
            deliberation_value="high",
            output_schema=None  # Free-text summaries
        )
    
    @classmethod
    def factual_qa(cls) -> "TaskProfile":
        return cls(
            name="factual_qa",
            answer_type="exact",
            normalizer=StructuredOutputNormalizer(answer_field="answer"),
            recommended_aggregation="vote",
            deliberation_value="medium",
            output_schema={"type": "object", "properties": {
                "reasoning": {"type": "string"},
                "answer": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1}
            }, "required": ["answer"]}
        )
```

The `CouncilAgent` uses the task profile to auto-configure:

```python
class CouncilAgent:
    async def complete(self, prompt: str, task_profile: Optional[TaskProfile] = None, **kwargs):
        profile = task_profile or self._infer_task_profile(prompt)
        
        # Auto-configure council for this task type
        council = self._configure_for_profile(profile)
        state = await council.arun(prompt)
        ...
    
    def _configure_for_profile(self, profile: TaskProfile) -> Council:
        """Select aggregation, termination, and protocol based on task type."""
        if profile.recommended_aggregation == "vote":
            aggregation = MajorityVote(normalizer=profile.normalizer)
            termination = AgreementThreshold(threshold=0.6, max_rounds=2)
        elif profile.recommended_aggregation == "synthesis":
            aggregation = MetaJudge(model=self.synthesis_model)
            termination = CompositeTermination([
                FixedRounds(max_rounds=3),
                BudgetExhaustion(max_cost=self.budget)
            ])
        elif profile.recommended_aggregation == "selection":
            aggregation = BestOfN()  # with LLM-as-judge instead of ground truth
            termination = FixedRounds(max_rounds=1)  # no deliberation needed
        
        return Council(
            agents=self.agents,
            topology=self.topology,
            protocol=self._get_protocol(profile),
            aggregation=aggregation,
            termination=termination,
            ...
        )
```

---

### Missing Abstraction 3: Confidence Estimation & Escalation

**The problem.** When a single LLM is uncertain, it hallucinates confidently. When a council disagrees, that disagreement is a *signal* — but the current system ignores it. The council always produces a final answer, regardless of whether the agents agreed or disagreed wildly.

**What's needed.** The council should be able to say "I'm not confident in this answer" and *escalate* — either to a human, to a more powerful council configuration, or to a retry with different models.

```python
@dataclass
class CouncilResponse:
    """The council's response, with calibrated confidence."""
    answer: str
    confidence: float           # 0-1, derived from inter-agent agreement
    agreement_ratio: float      # raw agreement metric
    dissenting_views: List[str] # what did dissenters say?
    cost: float
    rounds_used: int
    
    @property
    def is_confident(self) -> bool:
        return self.confidence >= 0.7
    
    @property
    def needs_escalation(self) -> bool:
        return self.confidence < 0.4

class CouncilAgent:
    async def complete_with_escalation(self, prompt: str, **kwargs) -> CouncilResponse:
        """Runs the council, and if confidence is low, escalates."""
        response = await self._run_council(prompt)
        
        if response.needs_escalation and self.escalation_strategy:
            response = await self.escalation_strategy.escalate(prompt, response)
        
        return response

class EscalationStrategy(abc.ABC):
    @abc.abstractmethod
    async def escalate(self, prompt: str, 
                       initial_response: CouncilResponse) -> CouncilResponse: ...

class UpgradeModels(EscalationStrategy):
    """Retry with more powerful models."""
    async def escalate(self, prompt, initial_response):
        # Replace gpt-4o-mini with gpt-4o, haiku with sonnet, etc.
        ...

class AddDeliberation(EscalationStrategy):
    """Run additional deliberation rounds focused on the disagreement."""
    async def escalate(self, prompt, initial_response):
        # Show agents the disagreement explicitly and ask them to resolve
        ...

class HumanInTheLoop(EscalationStrategy):
    """Flag for human review."""
    async def escalate(self, prompt, initial_response):
        return CouncilResponse(
            answer=initial_response.answer,
            confidence=initial_response.confidence,
            needs_human_review=True,
            dissenting_views=initial_response.dissenting_views,
            ...
        )
```

---

### Missing Abstraction 4: Cost-Quality Control Plane

**The problem.** The current system has no awareness of cost-quality tradeoffs. It always runs the full council (all models, all rounds), regardless of whether the query is "what is 2+2" or "summarize this 100-page legal document."

**What's needed.** A control plane that makes economic decisions:

```python
class CouncilPolicy:
    """Decides how to configure the council based on the query and budget."""
    
    def __init__(self, budget: float = 0.10, quality_target: str = "high"):
        self.budget = budget
        self.quality_target = quality_target
    
    async def plan(self, prompt: str, task_profile: TaskProfile) -> CouncilConfig:
        """Produces a council configuration that fits within budget."""
        
        # Estimate cost of different configurations
        configs = [
            CouncilConfig(
                name="fast_vote",
                agents=self.cheap_models[:3],
                protocol=NoneProtocol(),
                aggregation=MajorityVote(),
                max_rounds=0,
                estimated_cost=0.002
            ),
            CouncilConfig(
                name="standard_deliberation",
                agents=self.mid_models[:3],
                protocol=PeerReviewProtocol(),
                aggregation=MetaJudge(self.mid_models[0]),
                max_rounds=1,
                estimated_cost=0.02
            ),
            CouncilConfig(
                name="deep_council",
                agents=self.frontier_models[:5],
                protocol=DebateProtocol(anti_sycophancy=True),
                aggregation=MetaJudge(self.frontier_models[0]),
                max_rounds=3,
                estimated_cost=0.15
            ),
        ]
        
        # Filter by budget
        affordable = [c for c in configs if c.estimated_cost <= self.budget]
        if not affordable:
            affordable = [configs[0]]  # always fall back to cheapest
        
        # Select by quality target
        if self.quality_target == "high":
            return affordable[-1]  # most expensive affordable option
        elif self.quality_target == "balanced":
            return affordable[len(affordable) // 2]
        else:
            return affordable[0]  # cheapest
```

For your PDF summarization example, the flow would be:
1. User: `council.complete("Summarize this PDF: ...", budget=0.05, task="summarization")`
2. `CouncilPolicy` selects a 3-model council with 1 round of peer review + MetaJudge synthesis (fits in $0.05)
3. Three models independently summarize the PDF
4. They see each other's summaries and critique (noting: "Model A missed section 4", "Model B overemphasized the methodology")
5. MetaJudge synthesizes the best summary, incorporating critiques
6. Council reports confidence=0.85 (high agreement on key points, minor differences in emphasis)
7. Result: a summary that's more reliable than any single model's output

---

### Missing Abstraction 5: The Pipeline as Pure Function (Framework Independence)

**The problem.** The core pipeline logic is entangled with LangGraph. This makes it hard to test, hard to understand, and hard to use outside LangGraph.

**What's needed.** The pipeline should be a pure async function that LangGraph (or any other framework) can wrap:

```python
# council/core.py — THE core pipeline. No framework dependencies.

async def run_council(
    prompt: str,
    agents: List[AgentConfig],
    model_client: ModelClient,
    topology: Topology,
    protocol: Protocol,
    ranking: Ranking,
    aggregation: Aggregation,
    termination: TerminationStrategy,
    anonymize: bool = True,
    task_profile: Optional[TaskProfile] = None,
) -> CouncilResult:
    """Execute a complete council deliberation.
    
    This is the ONLY function that knows the full pipeline.
    It is a pure async function with no framework dependencies.
    """
    state = CouncilState.initial(prompt)
    agent_ids = [a.id for a in agents]
    
    # Stage 1: Independent Generation
    state = await _generate(state, agents, protocol, model_client, task_profile)
    
    # Stage 2-4: The Deliberation Loop
    # Rank and aggregate are INSIDE the loop so that the termination
    # strategy can check consensus on the aggregated state — not on raw
    # response text. This mirrors the academic peer review process: the
    # area chair reads and aggregates reviews before deciding whether to
    # invoke another discussion round.
    while True:
        answer_responses = _get_answer_round_responses(state, protocol)
        preferences = await _rank(state, ranking, agent_ids)
        agg_result = await _aggregate(answer_responses, aggregation, preferences)
        state.interim_result = agg_result
        
        should_stop, reason = await termination.should_terminate(state)
        if should_stop:
            state.termination_reason = reason
            break
        state = await _deliberate(
            state, agents, topology, protocol, model_client, anonymize
        )
    
    state.final_result = agg_result
    return state.to_result()

async def _generate(state, agents, protocol, model_client, task_profile):
    """Round 0: All agents respond independently."""
    tasks = []
    for agent in agents:
        ctx = VisibilityContext(
            agent_id=agent.id,
            round_index=0,
            visible_responses=[],
            own_previous_responses=[],
            total_agents=len(agents),
            communication_mode=CommunicationMode.INDIVIDUAL,
            original_prompt=state.question,
        )
        prompt = protocol.build_prompt(ctx)
        
        # Inject output schema if task profile specifies one
        if task_profile and task_profile.output_schema:
            prompt += f"\n\nRespond in JSON: {json.dumps(task_profile.output_schema)}"
        
        tasks.append(_call_agent(agent, prompt, model_client))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... process results into state ...
    return state

async def _deliberate(state, agents, topology, protocol, model_client, anonymize):
    """One round of deliberation."""
    round_idx = state.current_round + 1
    adj_matrix = topology.get_adjacency_matrix(round_idx)
    comm_mode = getattr(topology, 'communication_mode', CommunicationMode.INDIVIDUAL)
    
    tasks = []
    for r_idx, agent in enumerate(agents):
        # Build visibility context from topology
        visible = []
        for resp in state.round_history:
            s_idx = [a.id for a in agents].index(resp.agent_id)
            if adj_matrix[s_idx][r_idx] or resp.agent_id == agent.id:
                visible.append(resp)
        
        own_prev = [r for r in state.round_history if r.agent_id == agent.id]
        
        ctx = VisibilityContext(
            agent_id=agent.id,
            round_index=round_idx,
            visible_responses=_anonymize(visible, agent.id) if anonymize else visible,
            own_previous_responses=own_prev,
            total_agents=len(agents),
            communication_mode=comm_mode,
            original_prompt=state.question,
        )
        
        prompt = protocol.build_prompt(ctx)
        tasks.append(_call_agent(agent, prompt, model_client))
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... process results ...
    state.current_round = round_idx
    return state
```

Then LangGraph becomes a *thin adapter*:

```python
# council/adapters/langgraph_adapter.py
class LangGraphCouncil:
    """Optional LangGraph wrapper for persistence, streaming, visualization."""
    
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.graph = self._build_graph()
    
    def _build_graph(self):
        builder = StateGraph(CouncilState)
        builder.add_node("run", self._run_core)
        builder.set_entry_point("run")
        builder.add_edge("run", END)
        return builder.compile(checkpointer=MemorySaver())
    
    async def _run_core(self, state):
        result = await run_council(state["question"], **self.kwargs)
        return result.to_state_dict()
```

---

### Missing Abstraction 6: Council Memory (Cross-Invocation Learning)

**The problem.** Each council invocation is stateless. If you summarize 10 PDFs in a row, the council learns nothing about your preferences, writing style, or domain. A single LLM with a long context window would at least benefit from the conversation history.

**What's needed (future, post-thesis).** A lightweight memory system:

```python
class CouncilMemory:
    """Persists learnings across invocations."""
    
    async def record(self, prompt: str, result: CouncilResult):
        """Record what worked and what didn't."""
        self.observations.append({
            "task_type": result.task_profile.name,
            "config_used": result.config_name,
            "confidence": result.confidence,
            "agreement": result.agreement_ratio,
            "cost": result.cost,
        })
    
    async def recommend_config(self, prompt: str) -> Optional[CouncilConfig]:
        """Based on past performance, recommend a council configuration."""
        # If we've seen similar tasks before, use what worked
        similar = self._find_similar_tasks(prompt)
        if similar:
            best = max(similar, key=lambda o: o["confidence"])
            return self._config_from_name(best["config_used"])
        return None
```

---

## Part IV — The Ultimate Plan

This plan integrates the bug fixes from Part II, the new abstractions from Part III, and the original benchmarking goals from `plan.md` into a single coherent roadmap. The key architectural decision: **build the agent first, benchmark it second.**

### The Layered Architecture

```
┌───────────────────────────────────────────────────────┐
│  CouncilAgent (unified interface, drop-in LLM replacement)  │
│  - complete(prompt) -> response                             │
│  - confidence estimation, escalation, budget control        │
├───────────────────────────────────────────────────────┤
│  CouncilPolicy (auto-configuration)                         │
│  - task profile detection                                   │
│  - cost-quality tradeoff                                    │
│  - model selection                                          │
├───────────────────────────────────────────────────────┤
│  Core Pipeline: run_council() (pure async, no frameworks)   │
│  - generate → [deliberate → rank → aggregate → check] loop  │
│  - termination checks aggregated state, not raw text        │
│  - anonymization, structured output (response_format API)   │
├───────────┬──────────┬──────────┬─────────────────────┤
│ Topology  │ Protocol │ Ranking  │ Aggregation         │
│ (who sees │ (what    │ (extract │ (blind: vote on     │
│  whom)    │  they    │  prefs)  │  normalized answers;│
│           │  say)    │          │  informed: MetaJudge│
│           │          │          │  reads debate arc)  │
├───────────┴──────────┴──────────┴─────────────────────┤
│  ModelClient (LiteLLM wrapper)                              │
│  - caching, metering, fault injection, retries              │
├───────────────────────────────────────────────────────┤
│  Evaluation Layer (benchmark mode only)                     │
│  - metrics, baselines, Shapley, statistical tests           │
│  - MLflow, OpenTelemetry                                    │
└───────────────────────────────────────────────────────┘
```

### Phase 0: Foundation Corrections (Week 1)

**Goal**: Make the existing code *correct*. No new features; fix what's broken.

| # | Task | Files | Why |
|---|------|-------|-----|
| 0.1 | Fix `task_accuracy` fuzzy match — word-boundary + numerical extraction | `evaluation/metrics.py` | False positives invalidate all results |
| 0.2 | Fix `MajorityVote` — introduce `AnswerNormalizer` with structured output parsing | `council/aggregation.py`, new `council/normalizer.py` | Exact string comparison is meaningless on free text |
| 0.3 | Fix anonymization — centralize in utility function, apply to all protocols | `council/protocol.py` | DebateProtocol leaks agent IDs |
| 0.4 | Fix MetaJudge — configurable model, round-structured prompt | `council/aggregation.py` | Hardcoded model + flat input |
| 0.5 | Fix state accumulators — use LangGraph reducers | `council/pipeline.py` | Potential race condition on concurrent nodes |
| 0.6 | Fix `self_consistency` and `random_vote` baselines (they use broken MajorityVote) | `evaluation/baselines.py` | Baselines are measuring noise |

**Deliverable**: `python experiments/run.py` produces correct results on GSM8K mock data. All existing unit tests still pass.

**Validation**: Run 3 GSM8K problems with council vs baselines. Verify that `task_accuracy` correctly matches "72" but not "172". Verify that `MajorityVote` groups "The answer is 72" and "72" together.

---

### Phase 1: Architectural Redesign (Week 2-3)

**Goal**: Resolve the structural identity crisis. Build the correct abstractions.

| # | Task | Files | Why |
|---|------|-------|-----|
| 1.1 | Introduce `VisibilityContext` dataclass | new `council/context.py` | Makes topology→protocol contract explicit |
| 1.2 | Introduce `CommunicationMode` enum | `council/topology.py` | Differentiates Bus vs Complete at the semantic level |
| 1.3 | Refactor all protocols to use `build_prompt(ctx: VisibilityContext) -> str` | `council/protocol.py` | Clean single-agent prompt interface |
| 1.4 | Resolve chairman/MetaJudge — star topology becomes relay, no privileged agents | `council/topology.py`, `council/aggregation.py` | Eliminates philosophical contradiction |
| 1.5 | Extract core pipeline to `council/core.py` as pure async function | new `council/core.py`, refactor `council/pipeline.py` | Framework independence; testability |
| 1.6 | Implement multi-round PeerReview (alternating critique-revision) | `council/protocol.py` | Currently single-round only |
| 1.7 | Implement sliding-window context for SimultaneousProtocol | `council/protocol.py` | Prevent quadratic context growth |
| 1.8 | Introduce `AnswerNormalizer` as a first-class pipeline component | new `council/normalizer.py` | Answer extraction before aggregation, not after |
| 1.9 | Enforce structured JSON output via protocol prompt injection | `council/protocol.py` | Replaces fragile regex ranking extraction |

**Deliverable**: Complete refactored pipeline. New integration test demonstrates: topology controls visibility (ring agent sees only predecessor), protocol formats prompts correctly, anonymization works for all protocols, structured output parses reliably.

**Validation**: 
- Unit test: `StarTopology.get_adjacency_matrix()` returns complete graph (relay, not privileged agent)
- Unit test: `PeerReviewProtocol.build_prompt()` with `VisibilityContext(round_index=2)` produces a revision prompt, not a critique prompt
- Unit test: `StructuredOutputNormalizer.normalize('{"answer": 72, "reasoning": "..."}')` returns `"72"`
- Integration test: Full pipeline with 3 agents, 2 rounds peer review, structured output, Borda aggregation

---

### Phase 2: Termination & Control (Week 4)

**Goal**: Make the council intelligent about *when* to stop and *how much* to spend.

| # | Task | Files | Why |
|---|------|-------|-----|
| 2.1 | Implement `TerminationStrategy` abstraction with `FixedRounds`, `AgreementThreshold`, `BudgetExhaustion`, `CompositeTermination` | new `council/termination.py` | No adaptive stopping exists |
| 2.2 | Wire termination into core pipeline | `council/core.py` | Replace hardcoded `max_rounds` check |
| 2.3 | Implement `TaskProfile` with presets for math, factual_qa, summarization, creative | new `council/task_profile.py` | Different tasks need different council strategies |
| 2.4 | Add cost estimation to `ModelClient` (pre-call estimate based on prompt length + expected output) | `council/models.py` | Budget-aware termination needs cost prediction |

**Deliverable**: Council with `AgreementThreshold(0.8)` stops after 1 round on easy math (all 3 models agree on "72") but continues for 3 rounds on hard reasoning (models disagree).

**Validation**:
- Test: Easy problem → terminates after round 0, reason="Agreement 100% >= 80%"
- Test: Hard problem → runs 3 rounds, reason="Max rounds reached"
- Test: Budget=$0.001 → terminates after generation, reason="Budget exhausted"

---

### Phase 3: The Council as Agent (Week 5-6)

**Goal**: Build the `CouncilAgent` — the unified interface that makes the council a drop-in LLM replacement.

| # | Task | Files | Why |
|---|------|-------|-----|
| 3.1 | Implement `CouncilAgent` with `complete()` interface matching `ModelClient` | new `council/agent.py` | The "council as agent" vision |
| 3.2 | Implement `CouncilResponse` with confidence estimation from inter-agent agreement | `council/agent.py` | Council's unique advantage: calibrated confidence |
| 3.3 | Implement `CouncilPolicy` for auto-configuration based on task profile and budget | new `council/policy.py` | Self-contained decision-making |
| 3.4 | Implement `EscalationStrategy` (upgrade models, add rounds, flag for human) | `council/agent.py` | Handle low-confidence situations |
| 3.5 | Add Condorcet and Copeland aggregation methods | `council/aggregation.py` | Social choice theory from plan.md |
| 3.6 | Integration: `CouncilAgent` as LiteLLM-compatible custom provider | new `council/litellm_provider.py` | Ultimate composability — use council anywhere LiteLLM is used |

**Deliverable**: Working `CouncilAgent` that can be used like this:

```python
from council.agent import CouncilAgent

# Create a council agent with budget control
agent = CouncilAgent(
    models=["gpt-4o", "claude-sonnet-4-20250514", "gemini-2.0-flash"],
    budget=0.05,
    quality="high"
)

# Use it exactly like a single LLM
response = await agent.complete("Summarize this document: ...")
print(response.content)       # The synthesized summary
print(response.confidence)    # 0.87 — high agreement between models
print(response.cost)          # $0.034 — within budget
print(response.metadata["rounds_used"])  # 2
print(response.metadata["dissenting_views"])  # ["Model B emphasized methodology more"]
```

**Validation**:
- Test: `CouncilAgent.complete("What is 2+2?")` returns "4" with confidence > 0.9, cost < $0.01
- Test: `CouncilAgent.complete("Summarize: [complex text]")` returns synthesis with confidence, dissenting views
- Test: `CouncilAgent.complete("...", budget=0.001)` uses cheapest config
- Test: Low-confidence result triggers escalation

---

### Phase 4: Benchmark Infrastructure (Week 7-8)

**Goal**: Build the evaluation apparatus. Now that the agent works, measure *how well* it works.

| # | Task | Files | Why |
|---|------|-------|-----|
| 4.1 | MLflow integration — log params, metrics, artifacts per experiment | `experiments/run.py` | Systematic comparison |
| 4.2 | Complete `inter_rater_agreement` (Cohen's κ) | `evaluation/metrics.py` | Currently a stub |
| 4.3 | Complete AIPW estimator | `evaluation/statistical.py` | Currently oversimplified |
| 4.4 | Implement Hydra sweeps for systematic exploration | `experiments/sweep.py` | Topology × Protocol × Aggregation sweeps |
| 4.5 | Add task datasets: MMLU, TruthfulQA, HumanEval | `tasks/` | Beyond GSM8K |
| 4.6 | Implement diversity trajectory with real embeddings | `evaluation/metrics.py` | Track convergence / diversity collapse |
| 4.7 | Implement real Shapley value computation | `evaluation/shapley.py` | Per-model contribution attribution |
| 4.8 | Mixed-effects model for domain-specific random intercepts | `evaluation/statistical.py` | Control for task effects (currently stub) |

**Deliverable**: Full benchmark sweep: 4 topologies × 4 protocols × 5 aggregations × 3 datasets = 240 configurations. Results in MLflow with statistical significance tests.

---

### Phase 5: Pipeline Hardening (Week 9-10)

**Goal**: Fix the structural issues discovered during live pipeline testing. The core loop, aggregation paradigm, and structured output enforcement must be production-solid before hypothesis testing produces meaningful results.

**Why this phase exists.** Running the pipeline on real tasks (GSM8K with 3 paid models) revealed that:
- Models ignore JSON schema instructions in long prompts → answers arrive as prose → normalizer falls through to `strip().lower()` → every response looks unique → confidence collapses to 0.33 even on unanimous agreement
- The pipeline loop runs deliberation in a loop but rank+aggregate happen *after* the loop exits — so termination strategies check raw response text instead of aggregated consensus
- PeerReviewProtocol alternates answer rounds (even) and critique rounds (odd), but no layer declares this — aggregation receives critiques mixed with answers
- MetaJudge receives only final-round responses as a flat list, discarding the deliberation arc that gives multi-round councils their value

These are not feature gaps — they are correctness issues that make hypothesis testing (Phase 6) unreliable.

| # | Task | Files | Why |
|---|------|-------|-----|
| 5.1 | Force structured output via `response_format={"type": "json_object"}` at the API level for answer rounds | `council/models.py`, `council/context.py` | Prompt-level JSON schema is ignored when context is long; API enforcement is reliable |
| 5.2 | Restructure core loop — rank+aggregate inside the loop, termination checks `interim_result` | `council/core.py` | Termination must check aggregated consensus, not raw text. Mirrors the academic peer review model: area chair aggregates before deciding on another discussion round |
| 5.3 | Protocol declares answer vs deliberation rounds via `is_answer_round(round_index) -> bool` | `council/protocol.py` | Core pipeline must filter answer-round responses for aggregation without hardcoding round-parity logic |
| 5.4 | Debate-aware aggregation — `aggregate()` receives optional `round_history` parameter | `council/aggregation.py`, `council/context.py` | Blind aggregators (MajorityVote) ignore it; informed aggregators (MetaJudge) use the full debate arc to trace how consensus formed. See Issue 11 |
| 5.5 | Thread `response_format` through `ModelRequest` → `LiteLLMClient` for answer rounds | `council/models.py`, `council/core.py` | Completes the structured output enforcement chain from protocol → core → model client |
| 5.6 | End-to-end verification: 5-task GSM8K run with 3 paid models, all pipeline stages visible | `experiments/run.py` | Verify that confidence reflects actual agreement, debate transcripts show clean stage separation, and council beats the no-deliberation baseline |

**Deliverable**: `uv run python -m experiments.run --config configs/experiment/fast.yaml` produces confidence ≥ 0.9 on unanimous agreement, debate transcripts with clean GENERATE → DELIBERATE → RANK → AGGREGATE stages, and council accuracy ≥ baseline accuracy.

**Validation**:
- Test: 3 agents all answer "72" → confidence = 1.0 (not 0.33)
- Test: `response_format` is passed to LiteLLM for answer rounds, not for critique rounds
- Test: `AgreementThreshold` terminates early when aggregated consensus is reached
- Test: MetaJudge prompt contains round-structured debate history with phase labels
- Test: Council accuracy on 5-task GSM8K ≥ majority-vote-without-deliberation baseline

---

### Phase 6: Runner Configurability & Correctness Fixes ✅

**Goal**: Make the experiment runner fully configurable so that Phase 7 hypothesis testing can sweep over topologies, aggregations, and termination strategies. Fix the correctness issues discovered during code review that would invalidate sweep results.

**Why this phase exists.** Code review after Phase 5 revealed that `experiments/run.py` hardcodes `CompleteGraphTopology`, `MajorityVote`, `FixedRounds`, and `NullRanking` — the only varying dimension is protocol. The "4 topologies x 4 protocols x 5 aggregations x 3 datasets = 240 configurations" deliverable from Phase 4 is structurally impossible. Additionally, `_deliberate()` only passes round N-1 responses to the visibility context, which means `SimultaneousProtocol`'s sliding window is dead code. The `task_accuracy` smart matcher lacks numeric extraction (Issue 9 partial implementation), causing false negatives on currency/comma-formatted numbers. The `CouncilAgent` production path doesn't thread `answer_response_format`, so the structured output enforcement from Phase 5 only works via the benchmark runner. Finally, `StarTopology` is indistinguishable from `CompleteGraphTopology` (identical adjacency + identical communication mode), providing no experimental value.

| # | Task | Files | Status |
|---|------|-------|--------|
| 6.1 | Make topology/aggregation/ranking/termination configurable from YAML | `experiments/run.py`, all config YAMLs | ✅ |
| 6.2 | Fix `_deliberate()` to pass all prior-round responses (all rounds, not just N-1) | `council/core.py` | ✅ |
| 6.3 | Fix `_generate()` to use `topology.communication_mode` instead of hardcoded `INDIVIDUAL` | `council/core.py` | ✅ |
| 6.4 | Add numeric extraction to `task_accuracy` smart matcher — handles `$70,000`, commas, currency | `evaluation/metrics.py` | ✅ |
| 6.5 | Thread `answer_response_format` through `CouncilAgent` → `CouncilConfig` → `run_council()` | `council/agent.py`, `council/policy.py` | ✅ |
| 6.6 | Inject `output_schema` from `TaskProfile` into protocols built by `CouncilPolicy` | `council/policy.py` | ✅ |
| 6.7 | Differentiate `StarTopology` from `CompleteGraphTopology` via `CommunicationMode.RELAY` | `council/topology.py` | ✅ |

**Phase 6 Extensions (implemented on `feature/p6-aggregation-polish`):**

| # | Task | Files |
|---|------|-------|
| 6.8 | ruff + mypy correctness pass across `council/` | `council/*.py` |
| 6.9 | ruff fixes in `evaluation/` + broken diversity test fixture | `evaluation/metrics.py`, tests |
| 6.10 | Numeric extraction in `task_accuracy` — full Issue 9 closure | `evaluation/metrics.py` |
| 6.11 | Per-agent `temperature` and `max_tokens` overrides on `AgentConfig` | `council/core.py`, `council/models.py` |
| 6.12 | `TaskProfile.prompt_hint` → `VisibilityContext.task_hint` → Protocol injection on answer rounds only | `council/task_profile.py`, `council/context.py`, `council/protocol.py`, `council/core.py`, `council/policy.py`, `council/agent.py` |
| 6.13 | `MetaJudge` receives `original_prompt` to anchor synthesis | `council/aggregation.py`, `council/core.py` |
| 6.14 | Benchmark runner routes via per-dataset `TaskProfile` registry (`tasks/profiles.py`) | `tasks/profiles.py`, `experiments/run.py` |
| 6.15 | Per-agent `system_prompt` threaded through `AgentConfig` → `ModelRequest` → `LiteLLMClient` | `council/core.py`, `council/models.py` |
| 6.16 | YAML schema extension: each `council.models` entry is a bare string OR `{model, temperature?, max_tokens?, system_prompt?}` dict; `council.meta_judge` nested dict carries synthesis-judge overrides (`{model?, temperature?, max_tokens?, system_prompt?}`). Legacy `meta_judge_model: "..."` still works. `MetaJudge` accepts `system_prompt` kwarg, forwarded to its `ModelRequest`. | `experiments/run.py`, `council/aggregation.py`, `configs/experiment/fast.yaml` |

**Deliverable achieved**: runner accepts all topology/aggregation/termination/protocol combinations; `SimultaneousProtocol` windowing works end-to-end; `task_accuracy("$70,000", "70000")` → 1.0; `CouncilAgent.complete()` enforces structured output; per-dataset `TaskProfile` drives normalizer, output schema, and prompt hint from `tasks/profiles.py`. YAML configs expose the full per-agent and per-judge knob set (temperature, max_tokens, system_prompt) — `fast.yaml` is the canonical example.

---

### Phase 7: Hypothesis Testing (Week 13-14)

**Goal**: Test the hypotheses from `plan.md` using the benchmark infrastructure.

| # | Hypothesis | Config | What to measure |
|---|-----------|--------|-----------------|
| 7.1 | H1 (Diversity curve) | 1-model → 3-model → 5-model councils, same vs different families | Accuracy vs model diversity (non-monotonic?) |
| 7.2 | H3 (Diminishing returns) | Same council, vary max_rounds from 0 to 5 | Accuracy gain per round (logarithmic decay?) |
| 7.3 | H5 (Cardinal > Ordinal) | Borda vs WeightedVote vs Condorcet on same tasks | Which aggregation wins, and does Arrow's escape work? |
| 7.4 | H6 (Anti-sycophancy) | Same config ± anti_sycophancy=true | Accuracy difference, convergence speed |
| 7.5 | H10 (Adaptive termination) | FixedRounds vs AgreementThreshold vs BudgetExhaustion | Cost savings vs quality loss |
| 7.6 | NEW: Council-as-agent vs single LLM | `CouncilAgent.complete()` vs best single model | Accuracy, variance, confidence calibration |

**Deliverable**: Results tables with Wilcoxon p-values and bootstrap CIs. At least 3 confirmed/rejected hypotheses.

---

### Phase 8: Polish, Thesis Integration, and Production Demo (Week 15-16)

| # | Task | Why |
|---|------|-----|
| 8.1 | Streamlit dashboard for interactive exploration of benchmark results | Thesis defense demo |
| 8.2 | Production demo: PDF summarization via `CouncilAgent` | Shows the vision |
| 8.3 | Production demo: Code review via `CouncilAgent` | Another application |
| 8.4 | API reference documentation | Usability |
| 8.5 | Thesis chapter: architectural decisions with empirical justification | The payoff |
| 8.6 | Package publication to PyPI as `llm-council` | Community contribution |
| 8.7 | `CouncilAgent` as LiteLLM-compatible custom provider | `council/litellm_provider.py` — ultimate composability (deferred from Phase 3.6) |

---

### The Repository Structure (Revised)

```
llm-council/
├── council/
│   ├── __init__.py
│   ├── agent.py            # CouncilAgent — drop-in LLM replacement
│   ├── policy.py           # CouncilPolicy — auto-configuration
│   ├── core.py             # run_council() — pure async pipeline
│   ├── context.py          # VisibilityContext, CommunicationMode
│   ├── models.py           # ModelClient (LiteLLM wrapper)
│   ├── topology.py         # Communication graphs
│   ├── protocol.py         # Deliberation protocols
│   ├── ranking.py          # Preference extraction
│   ├── aggregation.py      # Decision methods (vote, synthesis, Condorcet)
│   ├── normalizer.py       # Answer extraction / normalization
│   ├── termination.py      # Adaptive stopping strategies
│   ├── task_profile.py     # Task-type-aware configuration
│   └── adapters/
│       └── langgraph.py    # Optional LangGraph wrapper
├── evaluation/
│   ├── metrics.py
│   ├── baselines.py
│   ├── shapley.py
│   └── statistical.py
├── tasks/
│   ├── loader.py
│   ├── gsm8k.py
│   └── registry.py
├── experiments/
│   ├── run.py
│   └── sweep.py
├── analysis/
│   ├── leaderboard.py
│   ├── plots.py
│   └── report.py
├── configs/               # Hydra YAML
├── tests/
├── pyproject.toml
├── plan.md               # Frozen research document
└── README.md
```

---

## Design Principles (The Constitution)

These are the immutable laws of the project. Every PR, every design decision, every line of code should be evaluated against them.

1. **The council is an agent, not a benchmark.** The benchmark measures the agent; the agent is the product. If a design decision helps benchmarking but hurts the agent interface, choose the agent.

2. **Same interface as a single LLM.** `council.complete(prompt) → response`. Any system that works with an LLM should work with a council, with zero code changes.

3. **Topology controls visibility. Protocol controls presentation. Aggregation controls decision.** Never let one layer do another's job. No privileged agents in the topology. No visibility filtering in the protocol. No prompt construction in the aggregation.

4. **Structured output over regex parsing.** When you need structured data from an LLM, ask for JSON at prompt time. Parse with `json.loads()`. Regex is a fallback, never the primary path.

5. **The council's unique value is calibrated confidence.** A single LLM guesses its confidence. A council *measures* it from inter-agent agreement. This signal drives termination, escalation, and user-facing reliability estimates.

6. **Every council run must beat majority-vote-without-deliberation.** If deliberation doesn't beat naive ensemble voting on the same models, the deliberation protocol is burning tokens. This is the "Debate or Vote" acid test.

7. **Cost is a first-class concern.** Every response includes its cost. Every configuration has an estimated cost. Budgets are enforced, not advisory.

8. **The core pipeline has zero framework dependencies.** `council/core.py` is pure Python + asyncio. LangGraph, Hydra, MLflow are at the edges, never in the core.

9. **Correctness before features.** A correct MajorityVote on 3 problems is worth more than a broken MajorityVote on 1000 problems with Shapley values and diversity trajectories.

10. **Anonymize by default.** Agent identities are a confound. Strip them during deliberation, preserve them in metadata for analysis.
