# AI Usage

## Tools

- **Claude (Anthropic), Opus model, in the claude.ai app**: design discussion, code generation, debugging, and drafting documentation.
- **A second, separate Claude chat**: an independent review of the finished codebase.

## How I worked with AI

I treated Claude like an engineer on my team and myself as the tech lead: I made the design decisions, Claude produced implementations, and I reviewed and tested everything before accepting it.

**Decisions I made up front** (Claude proposed options with tradeoffs; I chose):

- **FastAPI + PostgreSQL + React/TypeScript.** FastAPI and React are the stack I've shipped before, so I could review and defend every line. Postgres over SQLite because SQLite serializes writes and would hide concurrency bugs instead of handling them.
- **Qualified expenses as a merchant-category allowlist**, mirroring how card networks classify merchants, over matching merchant names, which is easy to fool.

**Where AI helped:**

| Area | What AI did | What I owned |
| --- | --- | --- |
| Data model | Drafted tables, constraints, integer cents, and the stored-balance + ledger design | Reviewed and accepted the design, and confirmed in `psql` that the constraints actually reject bad writes |
| Concurrency | Implemented the atomic conditional update and idempotency handling | Ran the mutation check myself to confirm the test fails without the fix |
| Tests | Wrote the pytest suite | Ran it on my own machine and reviewed what each concurrency test asserts |
| UI | Built the React components | Tested every flow by hand in the browser |
| Docs | Drafted README and architecture.md | Edited for accuracy against the code and against what I actually ran |

## Representative prompts and workflows

1. **Decisions first, as options.** I gave Claude the assignment and had it lay out the foundational choices (backend, database, frontend, how to classify qualified expenses) as options with tradeoffs and a recommendation. I chose each one before any code was written.
2. **Make the concurrency claim prove itself.** The concurrency test releases the $80 and $50 purchases at the same instant on separate database connections, 25 times. I temporarily replaced the atomic update with a naive read-then-write version and reran the tests: both purchases were approved, 30 simultaneous $10 purchases all went through against a $100 balance, and when deposits raced purchases, the final balance no longer matched what had actually been approved. A test that can't fail proves nothing, so this was the evidence the test works.
3. **Run it on my machine, feed results back.** Every change went through the same loop: rebuild with Docker, run the tests and the UI myself, and paste the real output back into the conversation. Most of the problems below surfaced this way rather than from reading code.

## Where AI output was wrong or incomplete

**Idempotency keys reused with different details.** The first version handled retries correctly: the same idempotency key returned the original result and prevented double charges. However, it only matched on the key. If a client reused a key for a different purchase, such as $75 instead of $25, the API quietly returned the old $25 result. No one was charged twice, but it would have masked a real client bug.

I missed this the first time I read through the code. I caught it by having a second Claude chat review the codebase independently, then checking its finding against the actual code myself. I accepted it: a key now has to match the original amount, merchant and category, otherwise the API returns 409. I also added a regression test covering a changed amount, category and merchant.

I didn't accept that review wholesale. It labeled this and a port-binding issue as "High" priority. The original behavior was safe, just unclear, and the port issue only mattered on a shared network. I fixed both because they were cheap, but treated them as hardening rather than bugs.

**Smaller things I caught by running it myself:**

- The Docker setup assumed host port 5433 was free. It wasn't on my machine, so the database failed to start. I moved it to an uncommon port and made all ports configurable, as described in the README.
- The README assumed local Python 3.11+. Mine is older, so installing the dependencies failed. I made running tests inside the backend container the default, so reviewers don't need Python installed.

**What I took from it:** AI-generated code usually does a good job with the main path but can overlook edge cases in the contract, like an input that partially matches a previous one. Running the system on my own machine and getting an independent review surfaced issues a passing test suite didn't.

## How I verified the final implementation

- **Automated tests:** 28 tests against real Postgres, covering every flow plus the concurrency suite (spec race ×25, 30-way race, concurrent retries, concurrent deposits at the limit, purchases racing deposits).
- **Mutation check:** swapped in a naive balance update, confirmed three concurrency tests fail, then restored the real one and confirmed all tests pass again.
- **Concurrency through the UI:** ran the $80/$50 test from the browser and checked the result against the database.
- **Database checks:** confirmed in `psql` that balance equals the ledger sum, and that Postgres rejects a ledger rewrite and a negative balance.
- **Manual walkthrough** of every UI flow in the README, including frozen cards, non-qualified merchants and the idempotent retry.
- **Second-opinion review:** a separate Claude chat reviewed the whole codebase. I accepted five findings (idempotency key reuse → 409, localhost-only ports, saving the retry request before sending it, resetting state when switching accounts, and more accurate wording about UUIDs) and downgraded their severity as described above.
- **Code review:** I read every file and can explain why each part exists.
