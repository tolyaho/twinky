# Live demo integration (API v1)

This is a local backend candidate for a future website. No website or API deployment is included.
One admitted job runs real Twitch capture, Deepgram transcription, vision captions and the existing
AudienceSignalAgent/EventIndex/provenance gate. It does not substitute stored outputs for live work.
The automated live-interface test uses real cached agent processing on recorded fixtures and is
explicitly labelled `recorded_fixture_test`. Actual Twitch/provider egress has not been validated
in this engineering pass. Rotate previously exposed credentials before any live smoke test.

## Run locally

Requirements: CPython 3.10+, POSIX process groups (Linux/macOS), ffmpeg on PATH, Streamlink and
network access to Twitch IRC/media/Helix and the configured inference providers. Windows process
group cleanup is not supported by this candidate. No database, broker or web framework is needed
for one process. The server binds loopback and uses the existing stdlib HTTP/SSE server.

```bash
make setup PYTHON=python3.12
make setup-record
# Export the names below using newly rotated values in the server environment.
# .env is not automatically loaded. Do not put secrets in URLs or browser code.
.venv/bin/python -m ts.cli serve --fixture evals/fixtures/stableronaldo_2026-08-30T0723 --port 8000
```

The fixture argument initializes the existing replay viewer; live session data uses a private
worker directory, not that fixture. The API can remain unavailable while replay works keylessly.

Environment variable **names only** (secret values must never be committed):

| variable | purpose |
|---|---|
| `TWINKY_LIVE_ENABLED` | explicit live admission opt-in |
| `TWINKY_DEMO_ACCESS_TOKEN` | backend bearer authentication; minimum 32 characters |
| `TWINKY_SESSION_CREDITS` | positive reserved number of starts for this process, maximum 20 |
| `TWINKY_ALLOWED_IPS` | exact allowed peer IPs; default loopback only |
| `TWINKY_EVIDENCE_TEXT` | opt-in text exposure only after privacy/rights review; default withheld |
| `TWITCH_CLIENT_ID` | registered Twitch app |
| `TWITCH_CLIENT_SECRET` | server-only client credentials grant; alternative to pre-issued token |
| `TWITCH_APP_ACCESS_TOKEN` | optional server-only app token instead of secret/grant |
| `TS_LLM_BASE_URL` | explicit HTTPS OpenAI-compatible endpoint supporting configured text and vision models |
| `TS_LLM_API_KEY` | server-only key for that endpoint |
| `DEEPSEEK_API_KEY` | legacy alternative key name; use the correct endpoint/model combination |
| `DEEPGRAM_API_KEY` | server-only STT key |
| `TS_TEXT_MODEL` | optional text model override; changes cache keys outside live jobs |
| `SSL_CERT_FILE` | optional system CA configuration |

Enable with the opt-in flag's documented value `1`, and text only with that flag set to `1`.
Keep text exposure off until owner review. Export actual token/secret values through your secret
manager. Model defaults match recorded GPT requests; the built-in provider's legacy default URL
is DeepSeek, so live admission requires an explicit HTTPS base URL. Do not send one provider's
key to another provider. Provider/model compatibility still needs a rotated-key smoke test.

Twitch lookup uses [Get Users](https://dev.twitch.tv/docs/api/reference/#get-users) with `login`,
then [Get Streams](https://dev.twitch.tv/docs/api/reference/#get-streams) with `user_id`.
An empty users response means `not_found`; an empty streams response for an existing user means
`offline`. Both accept an app token. The server can acquire one using the
[client credentials grant](https://dev.twitch.tv/docs/authentication/getting-tokens-oauth/#client-credentials-grant-flow).
Token responses, headers, IDs from OAuth and raw upstream error bodies are never returned.
The client caches grant tokens until near expiry; pre-issued invalid tokens produce `unavailable`.
For a long-running deployed OAuth integration, add the required periodic token validation lifecycle
and test refresh/revocation; this single-job worker does not maintain a durable OAuth session.

## HTTP contract

All `/api/sessions` methods require `Authorization: Bearer <backend-token>` and an allowed
socket peer IP. No query-string tokens or CORS wildcard. A future website should call through a
server-side adapter (BFF), which keeps the backend token and provider credentials out of browser
code. Native EventSource cannot set authorization headers: use a streaming fetch client through
that adapter, or an authenticated same-origin BFF SSE route. Do not place this shared token in JS.

Example requests below use placeholders, not real secrets:

```http
POST /api/sessions
Authorization: Bearer <backend-token>
Content-Type: application/json

{"channel":"example_channel","duration_seconds":60}
```

`channel` is a Twitch username, 1–25 ASCII letters/digits/underscore, normalized to lowercase.
URLs and extra JSON properties are rejected. This version supports one 60-second capture per
session; duration can be omitted or must equal 60. The 180-second end-to-end deadline includes
lookup, capture, enrichment and analysis; it is not a promise to finish all stages in that time.
The API immediately returns `202` with a generated `session_id` and current state:

```json
{"schema_version":1,"session_id":"<id>","channel":"example_channel","state":"queued",
 "source_mode":"live","last_seq":1,"result":null,"evidence_text":false}
```

Actual snapshots additionally include the machine-readable limits. A fast worker may already
have advanced beyond queued when the response is serialized.

| method and route | response |
|---|---|
| `GET /api/sessions/<id>` | snapshot, state, latest sequence, limits and completed result |
| `GET /api/sessions/<id>/events?after=0` | SSE envelopes; resume after sequence using query or `Last-Event-ID` |
| `DELETE /api/sessions/<id>` | `202` cancellation requested; poll until terminal/cleanup completes |

Lookup happens inside the bounded worker before capture. Intermediate states: `queued`,
`checking`, `running`. Terminal states: `not_found`, `offline`, `unavailable`, `failed`,
`timed_out`, `cancelled`, `completed`. A previously live channel can end or become unsupported
between lookup and capture; that is a pipeline failure, never fabricated offline evidence.
`completed` means processing finished; zero useful signals is possible. Provider/ingest failure
leads to `failed`; unconfigured providers/status service leads to `unavailable`.

Admission errors are JSON `{ "schema_version":1, "error":"<code>" }`: invalid body/channel/duration
400, missing/incorrect auth 401, peer not allowed 403, unknown/expired session 404, IP rate 429,
and unconfigured live mode/capacity/credits 503. Request bodies are capped at 1 KiB; chunked bodies
are rejected. Replay HTTP label lookup explicitly forces cache-only mode even if the parent environment
requests recording; it cannot bypass paid-session admission. The legacy unauthenticated paid
`/api/live` returns 410 with a migration pointer.
Operator capture/enrichment and Tier 0 chat still exist; a public proxy should expose only the
new session routes, not the legacy operator/replay endpoints.

## SSE envelope v1

```text
id: 4
event: progress
data: {"schema_version":1,"session_id":"<id>","seq":4,"type":"progress","elapsed_ms":61000,"source_mode":"live","data":{"phase":"enrichment","frames":2}}
```

Common fields: version, session ID, monotonically increasing `seq`, type, elapsed time from
admission, explicit source mode, typed data. Sequence is the cursor; elapsed time is operational
progress, not a historical event timestamp. Event payloads:

| type | data |
|---|---|
| `status` | state transition |
| `progress` | capture/enrichment/agent phase, step/max_steps or tool name/item count |
| `context` | channel status; modality event IDs/types/timestamps; cited chat evidence IDs/timestamps |
| `candidate_signal` | original card schema and `causal_claim: hypothesis` before gate |
| `provenance_decision` | signal_id, checks_passed, violation codes |
| `error` | stable safe code; no raw provider response/exception |
| `completion` | terminal state and result (or null) |

Result: original cards with gate decisions, gate version, steps and cache/usage counts. Legacy
card status `verified` means citation/time checks passed; titles, distributions and causal meaning
are not verified. Unknown trigger is different from a `none` abstention. The backend exposes
progress/tool summaries, not hidden chain-of-thought. It posts nothing to Twitch.

Evidence text, titles, quotes and distributions are withheld by default; stable IDs, timing,
types and mechanical verdicts remain. With text opt-in, this is private beta output requiring
operator review, not guaranteed anonymization. Authors/logins and private file paths are removed
in either mode. No raw video/audio is returned. Keep any future public UI honest about withheld
text and hypotheses. Existing frozen fixtures may still contain viewer mentions; this API does
not silently scrub or rewrite historical evidence.

## Enforced limits and remaining infrastructure

| resource | boundary |
|---|---|
| capture / total job | 60 seconds requested; parent process-group watchdog at 180 seconds including lookup |
| media input | 64 MiB read cap; ffmpeg 16 kHz mono WAV, 2,000,000-byte audio cap; max 2 frames scaled within 720×720 |
| enrichment | reject audio >2,000,000 bytes or any frame >1,000,000 bytes before provider calls |
| chat | at most 3,000 rows, 1,024 text characters per row; bounded WebSocket messages/queue |
| provider requests | reserve at most 1 STT + 2 vision + 4 agent calls; no application-level retries |
| requested completion | at most 4,200 aggregate output tokens (2×300 + 4×900) |
| text input | max 32,768 serialized UTF-8 bytes/request and 131,072 bytes/session; reject before request |
| concurrency / admission | 1 active reserved job, no waiting queue; 2 starts/allowed IP/hour; explicit non-refundable startup credits |
| jobs / results | max 20 retained jobs; snapshots expire after 15 minutes, pruned at next admission |
| events / HTTP | max 128 envelopes, 16 KiB each, result <=8 KiB; 16 HTTP handler slots, 30-second socket timeout; SSE reconnects after 25 seconds |
| temporary storage | private directory; 16 MiB watchdog threshold; delete after worker/process group is stopped and waited |
| cancel / failure | process group killed including ffmpeg; no capacity release until process exit and cleanup |

The watchdog polls about every 100 ms; these wall-time/disk thresholds can overshoot by polling,
scheduling and an in-flight write. The input-byte cap is checked per chunk before sending it to
ffmpeg. A server kill/crash cannot guarantee application cleanup. Use an isolated container with
hard memory/CPU/disk/pid quotas and an external job reaper before internet exposure. The candidate
does not install those infrastructure limits. The worker discards temporary captures, traces and
provider cache after completion, retaining only the bounded in-memory result/events until expiry.

Input bytes and requested completion tokens are scheduling controls, not exact provider-billed
token counts. STT audio seconds/image pricing, tokenization, changing prices, provider behavior
and already accepted requests after cancel mean actual USD spend is not strictly bounded here.
The old ledger/$3/600-second helper is estimate-only and is not used by the new API.

**Initial deployment recommendation: restricted/allowlisted beta.** A production BFF/reverse
proxy must add TLS, per-account authentication and rate limits, connection/body/time limits,
origin/CSRF controls appropriate to its auth, and provider account-level budgets. Ignore untrusted
X-Forwarded-For; this backend rates the socket peer, so one BFF shares that quota unless it adds
its own user/IP limiter. Run exactly one backend process: counters are in memory, reset on
restart, and are not a cross-worker billing reservation. Scaling requires an atomic shared quota/
job store, durable cancellation/cleanup and secret rotation. Fail closed if any required budget
or infrastructure cannot be reserved; do not expose arbitrary public paid starts with only a
client-side cap or the historical ledger estimate.

## Verification and next smoke test

Offline tests cover official endpoint shape/error handling, full HTTP admission → cached real
agent → gate → SSE/snapshot, cursor resume, offline/not-found without paid calls, reservation,
limits, cancellation, timeout and actual process-group cleanup. Test source mode is explicit.
No existing credential was used and no Twitch/paid request was made in those tests.

After owner-confirmed rotation and rights decisions, run an operator-only live smoke test with
one allowed channel/IP and a single startup credit. Confirm actual Helix status, capture support,
audio/frame quality, provider/model routing, timeout/cancellation, account usage and text privacy.
Only then describe that network path as validated. Do not deploy or publish the candidate without
separate approval.
