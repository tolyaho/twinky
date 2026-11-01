import { useEffect, useRef, useState } from "react";
import type { SemanticInfo } from "../semantic/live";
import { OverlayView, overlayUrl } from "./Overlay";
import type { GroupView, UiStatus } from "./useSession";

interface Props {
  channel: string;
  windowMs: number;
  groups: GroupView[];
  status: UiStatus;
  semantic?: SemanticInfo;
  onClose: () => void;
}

export const OVERLAY_SIZE = { width: 420, height: 240 };

/**
 * Setting the overlay up: the link, how to add it to OBS, and a preview. The preview draws this
 * page's own groups with the overlay's component — it does not open a second connection or load
 * the model twice. The link, opened in OBS, is its own page and connects by itself.
 */
export function OverlaySetup({ channel, windowMs, groups, status, semantic, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const [light, setLight] = useState(false);
  const [copied, setCopied] = useState<"yes" | "no" | null>(null);
  const url = overlayUrl(window.location.origin, channel, { light, windowMs });

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (typeof d.showModal === "function" && !d.open) d.showModal();
    const close = () => onClose();
    d.addEventListener("close", close);
    return () => d.removeEventListener("close", close);
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied("yes");
    } catch {
      setCopied("no"); // the field is selected instead, for ⌘C / Ctrl+C
      const input = ref.current?.querySelector<HTMLInputElement>(".ovs-url-input");
      input?.select();
    }
    window.setTimeout(() => setCopied(null), 2400);
  };

  // in the lighter mode the overlay has no topic model: reactions and exact repeats only
  const preview = light ? groups.filter((g) => g.rule === "reaction" || g.rule === "phrase") : groups;
  const previewSemantic: SemanticInfo | undefined = light ? { state: "off", pending: 0, textMessages: 0 } : semantic;

  return (
    <dialog ref={ref} className="ovs" aria-labelledby="ovs-title" onCancel={() => onClose()}>
      <div className="ovs-body">
        <h2 id="ovs-title" className="ovs-title">
          Show #{channel} chat on stream
        </h2>
        <p className="ovs-lede">
          An overlay for OBS: the {groups.length ? "same few groups" : "groups"} this board shows, on a transparent background, live. It
          connects to Twitch chat by itself, read-only — this page does not need to stay open.
        </p>

        <label className="ovs-label" htmlFor="ovs-url">
          Overlay link
        </label>
        <div className="ovs-url">
          <input
            id="ovs-url"
            className="ovs-url-input"
            readOnly
            value={url}
            onFocus={(e) => e.currentTarget.select()}
            spellCheck={false}
          />
          <button className="btn-light ovs-copy" onClick={copy}>
            {copied === "yes" ? "Copied" : "Copy"}
          </button>
        </div>
        <p className="ovs-hint" role="status">
          {copied === "no" ? "Couldn't copy automatically — the link is selected, press ⌘C or Ctrl+C." : "No key and no login in the link: it only reads public chat."}
        </p>

        <label className="ovs-opt">
          <input type="checkbox" checked={light} onChange={(e) => setLight(e.target.checked)} />
          <span>
            <strong>Lighter</strong> — reactions and repeated messages only. Skips the topic model: no 30 MB download in OBS,
            and next to no CPU.
          </span>
        </label>

        <div className="ovs-grid">
          <ol className="ovs-steps">
            <li>
              In OBS, under <strong>Sources</strong>, click <strong>+</strong> and choose <strong>Browser</strong>.
            </li>
            <li>Paste the link as the URL.</li>
            <li>
              Set width <strong>{OVERLAY_SIZE.width}</strong> and height <strong>{OVERLAY_SIZE.height}</strong>. Larger works too:
              the text scales with the width.
            </li>
            <li>Keep OBS's custom CSS as it is. The background is already transparent.</li>
          </ol>
          <figure className="ovs-preview">
            <div className="ovs-stage" style={{ aspectRatio: `${OVERLAY_SIZE.width} / ${OVERLAY_SIZE.height}` }}>
              <OverlayView channel={channel} groups={preview} status={status} semantic={previewSemantic} windowMs={windowMs} />
            </div>
            <figcaption>Preview from this page's chat. The checks stand for your stream.</figcaption>
          </figure>
        </div>

        <div className="ovs-foot">
          <a className="link-inline" href={url} target="_blank" rel="noopener">
            Open the overlay on its own
          </a>
          <button className="btn-ghost btn-ghost-lg" onClick={() => ref.current?.close()}>
            Done
          </button>
        </div>
      </div>
    </dialog>
  );
}
