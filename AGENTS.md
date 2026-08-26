- discuss each function and its requirment before implementing.
- Never not add silent returns or silent fails.
- start with the smallest direct implementation that could work. before expanding the plan, verify whether that implementation solves the observed problem. every extra function, abstraction, safeguard, or adjacent fix needs concrete evidence that it is required.
Example:
DO: If a library already accepts `/goal <objective>`, first wire that command into the existing call site and run one focused test.
DO: Expand the implementation only when the code or test proves the direct change is insufficient.
DON’T: Design helper layers, lifecycle state, polling, or recovery paths before testing the library’s built-in behavior.
DON’T: Add adjacent fixes or speculative edge-case handling that the request does not require.
- your job is to teach while building. you should ask me things to know if I am clear or not.
- before suggesting change, think how many line change will it be? can we be less? better if we are removing lines
- Tests are good! Endless smoke tests, "regression tests" for feature deletions, etc, much less good. Tests should be focused, not slop.
Example:
DO: Add focused tests for important behavior, edge cases, and likely failures.
DON’T: Add repetitive smoke tests or preserve tests for behavior that was intentionally removed.

- Try to keep each file smaller than 200-300 lines if possible. dont break just for that rule alone if it dosent make sense.
- when making change try to think if removing something will be better than adding a bandage fix.
Example:
DO: Remove outdated or unnecessary code causing the problem when that makes the system simpler.
DON’T: Add conditions, fallbacks, or workarounds that only hide the underlying problem.

- make a open pr when the change is more then a simple fix.
- make small focused commits.
- Using regex is frowned upon and only be used for a very small and specific and deterministic use case.
Example:
DO: Validate a fixed invoice ID format such as `INV-123456`.
DO: Remove a known prefix with regex.
DON’T: Parse HTML, JSON, addresses, bank statements, or human-written descriptions with regex.
DON’T: Use one large regex containing many optional groups and edge cases.
Use this file `~/resource_use` to log what you're using and remove that after use. If you see a resource you want is being used by someone else, then wait or use something else.
