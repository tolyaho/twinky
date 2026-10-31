import { useCallback, useState } from "react";
import { Landing } from "./ui/Landing";
import { Workspace } from "./ui/Workspace";
import { useSession, type Descriptor } from "./ui/useSession";
import type { ReplayRow } from "./engine/session";

export default function App() {
  const [descriptor, setDescriptor] = useState<Descriptor | null>(null);
  const view = useSession(descriptor);

  const watch = useCallback((channel: string) => {
    setDescriptor({ kind: "live", channel });
  }, []);

  const replay = useCallback(async () => {
    const mod = (await import("./data/replay.json")) as { default: ReplayRow[] } | ReplayRow[];
    const rows = (Array.isArray(mod) ? mod : mod.default) as ReplayRow[];
    setDescriptor({ kind: "replay", channel: "stableronaldo", rows });
  }, []);

  if (!descriptor) return <Landing onWatch={watch} onReplay={replay} />;
  return <Workspace view={view} onSwitch={watch} onBack={() => setDescriptor(null)} />;
}
