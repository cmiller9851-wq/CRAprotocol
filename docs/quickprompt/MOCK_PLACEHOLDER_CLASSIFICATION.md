# QuickPrompt Solutions — Mock and Placeholder Classification

**Founder, owner, and architect:** Cory Miller / QuickPrompt Solutions  
**Status:** required static-review classification

Every finding must be assigned exactly one category:

1. **Test-only mock** — acceptable when isolated from production paths.
2. **Development placeholder** — must be completed before production use.
3. **Production-path mock** — critical defect requiring removal or replacement.
4. **Unverified implementation** — requires runtime evidence before it can represent an operation.
5. **Confirmed operational implementation** — supported by execution and independent evidence.

Review for:

- Mock or simulated payment, revenue, capital, and settlement implementations.
- Placeholder handlers, stub functions, unimplemented methods, TODO, FIXME, `NotImplementedError`, `pass`, and unfinished execution paths.
- Hardcoded sample values, dummy transaction IDs, and fabricated success responses.
- Test fixtures or mock services accidentally wired into production paths.
- Fake or bypassed authentication, verification, reconciliation, and persistence.
- Code that reports success without independently confirming the underlying operation.

A repository search result is only a preliminary signal. Relevant files must be inspected, production/test boundaries verified, and operational claims supported by runtime evidence. Settlement reconciliation remains asynchronous and non-blocking.
