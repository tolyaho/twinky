// Small motion primitives. Motion here is feedback, not decoration: it shows that something
// changed and in which direction, and it never shows a value that was not real.
import { useRef } from "react";

export const EASE_OUT = "cubic-bezier(0.2, 0.7, 0.2, 1)";

/** CSS transitions honour the global reduced-motion rule; Web Animations must ask for themselves. */
export function motionAllowed(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    !window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * A number that rolls to its new value: the old value slides out, the new one slides in, in the
 * direction of change. Unlike a counting tween it never displays an intermediate value — every
 * frame shows a number that was actually measured.
 */
export function Num({
  value,
  text,
  className,
  emphasis,
}: {
  value: number | string;
  /** Display text, when it differs from `value` (e.g. "1.2k"). */
  text?: string;
  className?: string;
  /** Tint the arrival briefly — used when a group surges. */
  emphasis?: boolean;
}) {
  const shown = text ?? String(value);
  // Direction is decided once per change and kept until the next one, so re-renders between
  // changes do not cut the animation short. (Mutating a ref during render is safe here: the
  // result is the same however many times React renders.)
  const last = useRef<{ shown: string; value: number | string; dir: "up" | "down" | null }>({
    shown,
    value,
    dir: null,
  });
  if (last.current.shown !== shown) {
    const up =
      typeof value === "number" && typeof last.current.value === "number"
        ? value >= last.current.value
        : true;
    last.current = { shown, value, dir: up ? "up" : "down" };
  }
  const dir = last.current.dir;
  return (
    <span className={`num${className ? ` ${className}` : ""}`}>
      <span
        key={shown}
        className={dir ? `num-in num-${dir}${emphasis ? " num-emph" : ""}` : undefined}
      >
        {shown}
      </span>
    </span>
  );
}
