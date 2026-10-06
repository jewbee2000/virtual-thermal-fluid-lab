# Orchestrating the work

The current user request, revised implementation plan, and REQUIREMENTS.md govern
execution. The T01-only kickoff and pause-before-T02 instructions are archived.
Proceed M0/M1 then required M2–M7 with runnable learning checkpoints. Native
Windows desktop delegation works without custom CLI roles. One source writer
per checkout; coordinator may maintain contracts/tasks/docs while read-only
reviewers inspect. Current GitHub/publication work is explicitly authorized after
its gates. User selected MIT and confirmed starter authorship/Pico availability.

## Operating model

Use one coordinator plus up to three active children. The roles are implementation, physics review, test review and evidence review; schedule roles as needed rather than launching all four. The custom files use the current official standalone-agent schema [S12] and inherit your selected model. Choose stronger reasoning for numerical review in the client if supported. No fixed model name or API expenditure is required by this project.

Do not add an autonomous coding service before the project exists. Codex supplies spawning, follow-up and waiting; Git and tasks.json supply durable progress. This setup teaches the orchestration decisions that matter: bounded tasks, contracts, ownership, independent evidence and integration.

## A repeatable task cycle

1. Coordinator selects one ready ticket, records status and restates its acceptance criteria.
2. For a physics change, the physics reviewer independently derives the equation and expected limiting cases before reading implementation details where practical.
3. Implementation agent makes the bounded change. In the default shared checkout it is the only source writer. Review agents are read-only.
4. Test reviewer identifies an independent counterexample, executes targeted checks if the environment permits, and reports any untested claim.
5. Evidence reviewer checks source mappings, uncertainty claims and whether run manifests can reproduce conclusions. Rotate this role after other children finish if the cap is reached.
6. Coordinator integrates results, executes the declared checks, records evidence and closes or blocks the ticket. Do not accept a review without evidence or treat agreement as validation.
7. You inspect changed physics, assumptions, acceptance criteria and the resulting plot before beginning the next conceptual stage.

For efficiency, use one review cycle and at most one repair cycle per ticket before reassessing scope. Suggested ticket scope is 30–90 minutes of agent work; this is an operating budget, not an automatic runtime limit. Record elapsed time, touched files and unnecessary rework to learn whether delegation helped.

## Shared-checkout ownership

| Role | May change | Must not change |
| --- | --- | --- |
| Coordinator | task board, contracts, integrated docs, acceptance definitions | thresholds without rationale |
| Implementation | paths assigned in ticket | unrelated models and shared contracts |
| Physics reviewer | nothing by default; returns proposed derivation/checks | production implementation or test expectations |
| Test reviewer | nothing by default; proposes tests to coordinator | implementation to make tests pass |
| Evidence reviewer | nothing by default; returns claim corrections | model behavior and scientific status |

Read-only sandbox settings can be overridden by a parent runtime, so prompts and file ownership remain necessary. Current OpenAI docs describe inherited permissions [S12]. A reviewer may need a disposable writable output directory to execute checks; use a separate worktree/session if its policy prevents this, not unrestricted global permissions.

## Optional worktrees for independent writers

After creating the initial Git commit:

```bash
git worktree add -b work/numerics ../fluidlab-numerics main
git worktree add -b work/reporting ../fluidlab-reporting main
```

Launch a distinct Codex session in each worktree and assign disjoint tasks. Each worktree needs `uv sync --locked`. Avoid two writers editing the same contract. Each agent commits only its assigned files and returns its commit hash. Coordinator reviews `git show COMMIT` and cherry-picks approved commits sequentially on main. If a conflict concerns equations or schemas, resolve the scientific contract first; do not choose one side blindly.

Agents launched in one session are not automatically isolated worktree writers. This optional workflow is a human/coordinator-managed isolation pattern. It is not a claim that the CLI creates worktrees for every child.

## Handoff template

```text
Ticket / role:
Question answered:
Files changed or reviewed:
Sources and exact claims supported:
Equations and units checked:
Commands actually executed / results:
Independent oracle or counterexample:
Known assumptions and unassessed conditions:
Recommendation: accept / repair / block
Next dependency:
```

## Restart and recovery

After interruption, read tasks.json, the last Git diff and run manifests. Resume the active ticket; do not recreate completed work. If dependencies or model contracts changed, identify which evidence is stale and rerun only relevant checks. Preserve failed traces. If an agent cannot browse, use the source register and mark unsupported assertions as unresolved. If the client lacks custom roles, paste the corresponding prompt into a separate chat. No hidden orchestration dependency is required to run or understand the bench.
