import { useCallback, useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Landing } from "./ui/Landing";
import { Workspace } from "./ui/Workspace";
import { motionAllowed } from "./ui/motion";
import { useSession, type Descriptor } from "./ui/useSession";
import type { ReplayRow } from "./engine/session";
import { normalizeChannel } from "./twitch/parse";

// The URL is the source of truth for what is on screen, so a channel can be shared as a link
// (`/?channel=xqc`), survives a refresh, and the browser's back button returns to the landing page.
type Route = { kind: "live"; channel: string } | { kind: "replay" } | null;

function routeFromUrl(): Route {
  const q = new URLSearchParams(window.location.search);
  if (q.has("replay")) return { kind: "replay" };
  const channel = normalizeChannel(q.get("channel") ?? "");
  return channel ? { kind: "live", channel } : null;
}

function urlFor(route: Route): string {
  // `topics=off` (the word-rules board, src/semantic/enable.ts) is the visitor's choice for the
  // whole visit, so it survives navigation
  const off = new URLSearchParams(window.location.search).get("topics") === "off";
  const q = [!route ? "" : route.kind === "replay" ? "replay" : `channel=${route.channel}`, off ? "topics=off" : ""]
    .filter(Boolean)
    .join("&");
  return q ? `?${q}` : window.location.pathname;
}

async function loadReplay(): Promise<ReplayRow[]> {
  const mod = (await import("./data/replay.json")) as { default: ReplayRow[] } | ReplayRow[];
  return (Array.isArray(mod) ? mod : mod.default) as ReplayRow[];
}

/**
 * Cross-fade between the landing page and the workspace where the browser supports view
 * transitions. The swap itself is synchronous and immediate — the transition animates it, it
 * never delays it.
 */
function crossFade(update: () => void) {
  const d = document as Document & { startViewTransition?: (cb: () => void) => unknown };
  if (typeof d.startViewTransition !== "function" || !motionAllowed() || document.hidden) {
    update();
    return;
  }
  d.startViewTransition(() => flushSync(update));
}

export default function App() {
  const [descriptor, setDescriptor] = useState<Descriptor | null>(() => {
    const r = routeFromUrl();
    return r?.kind === "live" ? r : null;
  });
  const [replayPending, setReplayPending] = useState(false);
  const view = useSession(descriptor);
  const nav = useRef(0); // the latest navigation wins, even over a slower replay import
  const current = useRef(descriptor);
  current.current = descriptor;

  const show = useCallback((next: Descriptor | null) => {
    // only the landing <-> workspace change is a page change worth animating
    if ((current.current === null) !== (next === null)) crossFade(() => setDescriptor(next));
    else setDescriptor(next);
  }, []);

  const go = useCallback(
    async (route: Route, history: "push" | "replace" | "none") => {
      const id = ++nav.current;
      const url = urlFor(route);
      const here = window.location.pathname + window.location.search;
      if (history === "push" && url !== here && url !== window.location.search) {
        window.history.pushState(null, "", url);
      } else if (history === "replace") {
        window.history.replaceState(null, "", url);
      }
      setReplayPending(false);
      if (!route) show(null);
      else if (route.kind === "live") show({ kind: "live", channel: route.channel });
      else {
        setReplayPending(true);
        try {
          const rows = await loadReplay();
          if (id === nav.current) show({ kind: "replay", channel: "stableronaldo", rows });
        } finally {
          if (id === nav.current) setReplayPending(false);
        }
      }
    },
    [show],
  );

  useEffect(() => {
    const initial = routeFromUrl();
    // replace, not push: tidies `?channel=XQC` to `?channel=xqc` and drops a malformed one
    if (initial?.kind === "replay") void go(initial, "replace");
    else window.history.replaceState(null, "", urlFor(initial));
    const onPop = () => void go(routeFromUrl(), "none");
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [go]);

  const watch = useCallback((channel: string) => void go({ kind: "live", channel }, "push"), [go]);
  const replay = useCallback(() => void go({ kind: "replay" }, "push"), [go]);
  const back = useCallback(() => void go(null, "push"), [go]);

  if (!descriptor) return <Landing onWatch={watch} onReplay={replay} replayPending={replayPending} />;
  return (
    <Workspace
      view={view}
      onSwitch={watch}
      onBack={back}
      onReplay={replay}
      replayPending={replayPending}
    />
  );
}
