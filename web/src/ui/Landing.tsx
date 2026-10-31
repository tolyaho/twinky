import { useState } from "react";
import { normalizeChannel } from "../twitch/parse";

interface Props {
  onWatch: (channel: string) => void;
  onReplay: () => void;
  /** The recording is being fetched; the replay link shows that instead of looking dead. */
  replayPending: boolean;
}

const EXAMPLES = ["xqc", "hasanabi", "jynxzi", "stableronaldo", "caseoh_"];

/** Decorative only: scattered marks collapsing into ordered bars. Abstract, never real chat. */
function SignalMotif() {
  const bars = [62, 40, 30, 22, 16];
  return (
    <svg className="motif" viewBox="0 0 320 140" aria-hidden="true">
      <g className="motif-noise">
        {Array.from({ length: 46 }).map((_, i) => (
          <circle
            key={i}
            cx={6 + ((i * 53) % 150)}
            cy={10 + ((i * 29) % 120)}
            r={1.6 + ((i * 7) % 3) * 0.5}
          />
        ))}
      </g>
      <g className="motif-bars" transform="translate(186,18)">
        {bars.map((w, i) => (
          <rect key={i} x={0} y={i * 24} width={w} height={12} rx={6} />
        ))}
      </g>
      <path className="motif-flow" d="M150,70 C168,70 170,70 186,42" />
    </svg>
  );
}

export function Landing({ onWatch, onReplay, replayPending }: Props) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (raw: string) => {
    const channel = normalizeChannel(raw);
    if (!channel) {
      setError("Enter a Twitch username, e.g. xqc — letters, numbers and underscores only.");
      return;
    }
    setError(null);
    onWatch(channel);
  };

  return (
    <main className="landing">
      <nav className="nav">
        <div className="wordmark">
          Twinky<span className="wordmark-dot">.</span>
        </div>
        <button
          className="link-btn"
          onClick={onReplay}
          disabled={replayPending}
          aria-busy={replayPending || undefined}
        >
          {replayPending ? (
            <>
              <span className="spinner" aria-hidden="true" />
              Loading the recording…
            </>
          ) : (
            "Watch a recorded example →"
          )}
        </button>
      </nav>

      <section className="hero">
        <div className="hero-copy">
          <h1 className="hero-title">
            Read the room,
            <br />
            <em className="hero-em">as it reacts.</em>
          </h1>
          <p className="hero-lede">
            Twinky turns a fast-moving Twitch chat into the few things the audience is actually
            saying — grouped, counted, and updating live as they say it.
          </p>

          <form
            className="channel-form"
            onSubmit={(e) => {
              e.preventDefault();
              submit(value);
            }}
          >
            <div className={`channel-field${error ? " channel-field-err" : ""}`}>
              <span className="channel-hash">#</span>
              <input
                className="channel-input"
                value={value}
                onChange={(e) => {
                  setValue(e.target.value);
                  if (error) setError(null);
                }}
                placeholder="enter a twitch channel"
                aria-label="Twitch channel"
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
              />
              <button className="btn-primary" type="submit">
                Watch live
              </button>
            </div>
            {error ? (
              <p className="channel-error" role="alert">
                {error}
              </p>
            ) : (
              <p className="channel-hint">
                No account, no setup. Your browser connects to Twitch directly — nothing is stored.
              </p>
            )}
          </form>

          <div className="examples">
            <span className="examples-label">Try</span>
            {EXAMPLES.map((c) => (
              <button
                key={c}
                className="chip"
                onClick={() => {
                  setValue(c);
                  submit(c);
                }}
              >
                {c}
              </button>
            ))}
          </div>
        </div>

        <aside className="hero-aside" aria-hidden="true">
          <SignalMotif />
          <div className="aside-note">
            <span className="aside-k">225 messages</span>
            <span className="aside-arrow">becomes</span>
            <span className="aside-v">3 things the room is doing</span>
          </div>
        </aside>
      </section>

      <section className="how">
        <div className="how-step">
          <span className="how-n">1</span>
          <h3>Enter a channel</h3>
          <p>Any live Twitch streamer. We connect to their public chat anonymously, in your browser.</p>
        </div>
        <div className="how-step">
          <span className="how-n">2</span>
          <h3>Watch it group</h3>
          <p>
            Repeated reactions, emote waves, shared words and audience questions collapse into a few
            readable signals — recounted every second or two.
          </p>
        </div>
        <div className="how-step">
          <span className="how-n">3</span>
          <h3>Read the room</h3>
          <p>
            Counts rise and fade with the moment. Open any signal to see the real messages behind
            it. No AI guesses — just arithmetic over what was said.
          </p>
        </div>
      </section>

      <footer className="landing-foot">
        <span>Deterministic clustering · no model calls · built on the Twinky research repo</span>
      </footer>
    </main>
  );
}
