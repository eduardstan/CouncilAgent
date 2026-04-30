# Email template — requesting MCMAS access (BACKUP procedure)

> **Status (2026-04-30):** A working download URL was found at
> <https://sail.doc.ic.ac.uk/software/mcmas/> — see
> [`docs/install_spot.md`](install_spot.md) §"MCMAS — verified install" for the
> verified install steps. **You probably do NOT need to send this email.**
>
> Keep this template only as a backup for: (a) requesting a binary for a
> non-Linux-x86_64 platform; (b) academic-courtesy citation if the
> maintainers' usage-tracking form is preferred over the direct download.
>
> Send to `mcmas@imperial.ac.uk` from your institutional email address
> (`@unimib.it` for the user). The MCMAS manual at
> <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf> §1 documents the
> email-request procedure for non-default platforms.

## Suggested subject

> Access request: MCMAS pre-compiled binary for Linux x86_64 (academic use,
> University of Milano-Bicocca)

## Suggested body

> Dear MCMAS maintainers,
>
> I am Eduard Ionel STAN, a researcher at the Department of Informatics,
> Systems and Communication of the University of Milano-Bicocca, Italy. I am
> writing to request access to a pre-compiled MCMAS binary for Linux x86_64
> (Ubuntu 24.04), as instructed in §1 of the MCMAS user manual at
> <https://sail.doc.ic.ac.uk/software/mcmas/manual.pdf>.
>
> I am developing **CouncilAgent‑NS**, an open-source neuro-symbolic
> multi-LLM council framework that uses LTL_f runtime monitoring (via SPOT)
> together with offline epistemic-strategic verification of council protocol
> automata. MCMAS is the natural verifier for the CTLK and ATL formulae I
> need to discharge. The work targets a series of publications at
> AAMAS 2027 (verified deliberation, P1) and AAAI 2027 (strategic gradual
> argumentation, P2), with the relevant theory recorded in
> `docs/theory.md` of the project repository.
>
> Concretely, the project includes a Trace → ISPL emitter
> (`council/symbolic/verify/ispl.py`) that I have already validated by 24
> structural unit tests. To complete the W1 (verification spine) acceptance
> criterion I need to run MCMAS on a 4-agent / 4-round example to
> verify two CTL properties (`EventuallyDecide`, `RefutationReachable`).
> Without the binary I am currently substituting NuSMV for the CTL
> fragment; for the CTLK / ATL properties that motivate publication P1 §3
> a working MCMAS instance is required.
>
> If you can share an MCMAS binary suitable for Linux x86_64 under terms
> consistent with academic, non-commercial use, I would gladly cite MCMAS
> (Lomuscio, Qu, Raimondi, *MCMAS: an open-source model checker for the
> verification of multi-agent systems*, STTT 2017) in every publication
> that depends on it, and acknowledge the maintainers in the project
> README and Zenodo record.
>
> If a license agreement form is needed, please send it and I will return
> it signed. I am also happy to provide additional context about the
> project's scope or licensing model.
>
> Thank you for your time and for maintaining MCMAS.
>
> Kind regards,
> Eduard Ionel STAN
> PhD researcher, University of Milano-Bicocca
> ioneleduard.stan@unimib.it

## What to do once a binary arrives

1. Place `mcmas` somewhere on `PATH` (e.g. `~/.local/bin/mcmas`, ensure executable).
2. Verify: `mcmas -version` should print the version banner.
3. Re-run the W1 acceptance test:
   ```bash
   RUN_INTEGRATION=1 uv run pytest tests/integration/test_mcmas_offline.py -v
   ```
4. If you obtained a NEW MCMAS binary (e.g. for a different platform than the
   linux64 build covered in ADR 0004), record the version + date in a follow-up
   ADR that supplements ADR 0004. Do NOT rewrite ADR 0004 in place.
5. If [`docs/install_spot.md`](install_spot.md) needs updating (e.g. macOS or
   Windows install steps), add a new subsection rather than replacing the
   existing linux64 instructions.
