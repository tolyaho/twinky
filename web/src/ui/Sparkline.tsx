interface Props {
  data: number[];
  /** First bucket we were actually listening for; earlier buckets are not drawn as zeros. */
  from?: number;
  width?: number;
  height?: number;
  label?: string;
}

/** A tiny inline-SVG area sparkline. Values are message counts per 10s bucket. */
export function Sparkline({ data, from = 0, width = 220, height = 44, label }: Props) {
  const n = data.length;
  const start = Math.min(Math.max(0, from), Math.max(0, n - 1));
  const seen = data.slice(start);
  const max = Math.max(1, ...seen);
  const stepX = n > 1 ? width / (n - 1) : width;
  const y = (v: number) => height - 3 - (v / max) * (height - 6);
  const x = (i: number) => ((start + i) * stepX).toFixed(1);
  const pts = seen.map((v, i) => `${x(i)},${y(v).toFixed(1)}`);
  const line = pts.length > 1 ? "M" + pts.join(" L") : "";
  const area =
    pts.length > 1 ? `M${x(0)},${height} L${pts.join(" L")} L${x(seen.length - 1)},${height} Z` : "";

  return (
    <svg
      className="spark"
      viewBox={`0 0 ${width} ${height}`}
      width="100%"
      height={height}
      preserveAspectRatio="none"
      role="img"
      aria-label={label ?? "Message rate over the window"}
    >
      {start > 0 && (
        // the part of the window before we connected: unknown, not zero
        <line
          className="spark-unknown"
          x1={0}
          x2={x(0)}
          y1={height - 3}
          y2={height - 3}
        />
      )}
      {area && <path d={area} className="spark-area" />}
      {line && <path d={line} className="spark-line" />}
      {seen.length > 0 && (
        <circle cx={x(seen.length - 1)} cy={y(seen[seen.length - 1]).toFixed(1)} r="2.4" className="spark-dot" />
      )}
    </svg>
  );
}
