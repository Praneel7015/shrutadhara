# ai privacy review

Completed fresh-context reviewer. Findings normalized by the Elephant; original IDs preserved. Full qualifications, disagreements and evidence are in the consolidated report.

## AI-01: A native-audio refusal does not stop later submissions

Mapped to F11, Major, Reproduced. `shrutadhara/processing.py:346; shrutadhara/processing.py:842; shrutadhara/processing.py:869`.

A schema-valid audio_received=false result becomes MeetingError, but only AIError breaks the loop. The local stub was called for both chunks after its first refusal.

The program continues unnecessary data submissions and quota use after capability failure, contrary to its documented stop policy. Existing consent was present; this is not a claim of upload without initial consent.

Recommendation: Introduce provider-neutral session-fatal/capability refusal categories. Stop subsequent calls, persist a blocked reason and retain unprocessed intervals. Keep specific size-limit splitting.

Test: Three mocked chunks, first native-audio refusal: exactly one submission, incomplete coverage and durable diagnostics.

## AI-05: Terminating Q&A/probe can leave the provider alive

Mapped to F12, Major, Reproduced. `shrutadhara/agy.py:244; shrutadhara/agy.py:256; shrutadhara/cli.py:515; shrutadhara/cli.py:534`.

Only process translates SIGTERM into handled cancellation. Other hosted paths spawn a new provider session; default parent SIGTERM bypasses its cleanup. A harmless fake agy survived parent termination.

A hosted request may continue after the initiating application exits. No actual provider was contacted in this review.

Recommendation: Wrap every hosted entry point with shared cancellation handling and process-group teardown; restore signal handlers and mark attempts cancelled. Also handle supervisor hard-death lifetime.

Test: Fake agy records PID then waits; terminate ask/probe parents and require no surviving child, released locks and interrupted attempt state.

## AI-02: Historical Q&A links point into a mutable transcript

Mapped to F13, Major, Reproduced. `shrutadhara/questions.py:129; shrutadhara/questions.py:176; shrutadhara/processing.py:503; shrutadhara/processing.py:555`.

Answers link to sequential IDs in the overwritten shared transcript. A local stub answer stayed unchanged while its cited anchor was replaced by contradictory synthetic dialogue.

Retained answers can appear supported by different evidence after correction or retranscription.

Recommendation: Save immutable transcript revisions or minimal evidence snapshots per question, and qualify links with revision identity. Reuse existing source hashes; do not add a database for this.

Test: Ask, correct/reorder/delete source segments, then open historical evidence. It must still show the originally cited text and revision.

## AI-03: Model text is rendered as active Markdown

Mapped to F14, Major, Reproduced payload; viewer effect untested. `shrutadhara/processing.py:551; shrutadhara/processing.py:698; shrutadhara/processing.py:705`.

Transcript and notes preserve model-authored images/links/HTML. Synthetic remote-image markup survived both renderers; no viewer was opened.

Forged links can misrepresent evidence. Remote-resource-capable viewers may make network requests when opened; actual fetching is viewer-dependent and was not tested.

Recommendation: Centralize literal text escaping, keep app-generated evidence links separate and retain exact raw transcript text in JSON. Support code through controlled rendering.

Test: Images, HTML, headings, forged evidence links and table escapes must render literally; generated local evidence links remain usable.

## AI-04: A single large segment bypasses notes request bounds

Mapped to F15, Major, Reproduced. `shrutadhara/processing.py:625; shrutadhara/processing.py:659; shrutadhara/processing.py:664`.

The splitter checks size only for a nonempty block and counts characters. A 200000-character Devanagari segment reached a local stub as a 601032-byte prompt.

Large requests can exceed provider limits or consume unintended quota; existing resumable behavior does not impose a bound on every request.

Recommendation: Check complete serialized UTF-8 request size before each call, including instructions. Reject oversized single segments before submission or split them into explicitly linked spans.

Test: Single oversize segment, many ordinary segments and multibyte text; no over-budget prompt may reach the adapter.

## AI-06: Cached output has no independent accepted-output digest

Mapped to F16, Major, Source verified; integrity scope. `shrutadhara/processing.py:803; shrutadhara/processing.py:837; shrutadhara/processing.py:597; shrutadhara/processing.py:640`.

Input fingerprints do not detect a schema-valid cached transcript/notes edit that preserves its fingerprint.

Accidental or same-user cached-output changes can silently alter provenance. This is not a remote compromise or protection against an attacker able to rewrite every baseline.

Recommendation: Separate accepted output revisions/digests from disposable input-keyed caches. Explicit imports create an auditable new revision. Align the baseline promise in SECURITY.md with the implemented scope.

Test: Modify valid cached text without changing input fingerprint; require rejection/invalidation. Explicit correction imports remain supported.

## AI-07: The ten-minute deadline is per attempt

Mapped to F22, Nit, Source verified. `README.md:142; shrutadhara/agy.py:209; shrutadhara/agy.py:255; shrutadhara/agy.py:317`.

Each of three attempts gets the full configured600seconds.

A chunk may take roughly30minutes plus cleanup/backoff, not one ten-minute total deadline.

Recommendation: State per-attempt and total bounds explicitly, or implement one shared overall deadline.

Test: A fake clock verifies retry allocation and total elapsed budget.

