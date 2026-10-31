import { useCallback, useEffect, useRef, useState } from "react";
import { Landing } from "./ui/Landing";
import { Workspace } from "./ui/Workspace";
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
  if (!route) return window.location.pathname;
  return route.kind === "replay" ? "?replay" : `?channel=${route.channel}`;
}

async function loadReplay(): Promise<ReplayRow[]> {
  const mod = (await import("./data/replay.json")) as { default: ReplayRow[] } | ReplayRow[];
  return (Array.isArray(mod) ? mod : mod.default) as ReplayRow[];
}

export default function App() {
  const [descriptor, setDescriptor] = useState<Descriptor | null>(() => {
    const r = routeFromUrl();
    return r?.kind === "live" ? r : null;
  });
  const view = useSession(descriptor);
  const nav = useRef(0); // the latest navigation wins, even over a slower replay import

  const go = useCallback(async (route: Route, history: "push" | "replace" | "none") => {
    const id = ++nav.current;
    const url = urlFor(route);
    const here = window.location.pathname + window.location.search;
    if (history === "push" && url !== here && url !== window.location.search) {
      window.history.pushState(null, "", url);
    } else if (history === "replace") {
      window.history.replaceState(null, "", url);
    }
    if (!route) setDescriptor(null);
    else if (route.kind === "live") setDescriptor({ kind: "live", channel: route.channel });
    else {
      const rows = await loadReplay();
      if (id === nav.current) setDescriptor({ kind: "replay", channel: "stableronaldo", rows });
    }
  }, []);

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

  if (!descriptor) return <Landing onWatch={watch} onReplay={replay} />;
  return <Workspace view={view} onSwitch={watch} onBack={back} />;
}
