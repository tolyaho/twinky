interface Props {
  data: number[];
  width?: number;
  height?: number;
  label?: string;
}

/** A tiny inline-SVG area sparkline. Values are message counts per 10s bucket. */
export function Sparkline({ data, width = 220, height = 44, label }: Props) {
  const n = data.length;
  const max = Math.max(1, ...data);
  const stepX = n > 1 ? width / (n - 1) : width;
  const y = (v: number) => height - 3 - (v / max) * (height - 6);
  const pts = data.map((v, i) => `${(i * stepX).toFixed(1)},${y(v).toFixed(1)}`);
  const line = pts.length ? "M" + pts.join(" L") : "";
  const area = pts.length
    ? `M0,${height} L${pts.join(" L")} L${((n - 1) * stepX).toFixed(1)},${height} Z`
    : "";

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
      {area && <path d={area} className="spark-area" />}
      {line && <path d={line} className="spark-line" />}
      {n > 0 && (
        <circle
          cx={((n - 1) * stepX).toFixed(1)}
          cy={y(data[n - 1]).toFixed(1)}
          r="2.4"
          className="spark-dot"
        />
      )}
    </svg>
  );
}
