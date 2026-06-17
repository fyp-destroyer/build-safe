import { useEffect, useMemo, useState } from "react";

interface TypewriterTextProps {
  text: string;
  animate?: boolean;
  className?: string;
}

export function TypewriterText({
  text,
  animate = true,
  className,
}: TypewriterTextProps): JSX.Element {
  const words = useMemo(() => text.split(/\s+/).filter(Boolean), [text]);
  const [visibleCount, setVisibleCount] = useState(animate ? 0 : words.length);

  useEffect(() => {
    if (!animate) {
      setVisibleCount(words.length);
      return;
    }

    setVisibleCount(0);
    if (words.length === 0) {
      return;
    }

    const chunkSize = words.length > 28 ? 2 : 1;
    const interval = window.setInterval(() => {
      setVisibleCount((current) => {
        const nextValue = Math.min(current + chunkSize, words.length);
        if (nextValue >= words.length) {
          window.clearInterval(interval);
        }
        return nextValue;
      });
    }, words.length > 42 ? 26 : 34);

    return () => window.clearInterval(interval);
  }, [animate, words]);

  const visibleText = animate
    ? words.slice(0, visibleCount).join(" ")
    : text;

  return (
    <span className={className}>
      {visibleText}
      {animate && visibleCount < words.length ? (
        <span className="ml-1 inline-block h-[1em] w-[0.08em] animate-pulse rounded-full bg-current align-[-0.15em]" />
      ) : null}
    </span>
  );
}
