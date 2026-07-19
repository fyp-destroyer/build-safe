"use client";

import { useEffect, useRef } from "react";

/**
 * Canvas2D re-implementation of a WebGL dot-matrix reveal effect — a wave of
 * dots fading in from the center, or fading out from the edges inward on
 * `reverse`. Deliberately not using three/@react-three/fiber: the visual is
 * fundamentally a 2D grid animation and doesn't need a 3D engine.
 *
 * Per design.md §9.2.
 */
export function DotMatrixReveal({
  reverse = false,
  animationSpeed = 3,
  dotSize = 3,
  cellSize = 20,
}: {
  reverse?: boolean;
  animationSpeed?: number;
  dotSize?: number;
  cellSize?: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;
    let cols = 0;
    let rows = 0;
    let rand: Float32Array = new Float32Array(0);
    let opacityTier: Float32Array = new Float32Array(0);

    const OPACITIES = [0.3, 0.3, 0.3, 0.5, 0.5, 0.5, 0.8, 0.8, 0.8, 1];

    function hash(x: number, y: number) {
      const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123;
      return s - Math.floor(s);
    }

    function resize() {
      if (!canvas) return;
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = width * dpr;
      canvas.height = height * dpr;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);

      cols = Math.ceil(width / cellSize) + 1;
      rows = Math.ceil(height / cellSize) + 1;
      rand = new Float32Array(cols * rows);
      opacityTier = new Float32Array(cols * rows);
      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const idx = j * cols + i;
          rand[idx] = hash(i, j);
          opacityTier[idx] = OPACITIES[Math.floor(hash(i + 0.5, j + 0.5) * OPACITIES.length)];
        }
      }
    }

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    let raf = 0;
    const start = performance.now();

    function frame(now: number) {
      if (!ctx) return;
      // Recomputed every frame (cheap) — see ⚠️ note in design.md §9.2 for why
      // this can't be hoisted outside the loop: at the time of the very first
      // resize(), the canvas hasn't laid out yet (clientWidth/clientHeight
      // are 0), so a value computed only once would freeze the render at a
      // meaningless center point and no dots would ever appear.
      const centerCol = cols / 2;
      const centerRow = rows / 2;
      const maxDist = Math.hypot(centerCol, centerRow);
      const t = ((now - start) / 1000) * animationSpeed * 0.35;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#000";
      ctx.fillRect(0, 0, width, height);

      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const idx = j * cols + i;
          const dist = Math.hypot(i - centerCol, j - centerRow);
          let opacity: number;

          if (reduceMotion) {
            opacity = opacityTier[idx];
          } else if (reverse) {
            const offset = (maxDist - dist) * 0.35 + rand[idx] * 2.2;
            opacity = t > offset ? 0 : opacityTier[idx];
          } else {
            const offset = dist * 0.35 + rand[idx] * 2.2;
            opacity = t > offset ? opacityTier[idx] : 0;
          }

          if (opacity <= 0.01) continue;
          ctx.globalAlpha = opacity;
          ctx.fillStyle = "#F97316"; // brand orange dots, not white — deliberately always-dark hero
          ctx.beginPath();
          ctx.arc(i * cellSize + cellSize / 2, j * cellSize + cellSize / 2, dotSize / 2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;

      if (!reduceMotion) raf = requestAnimationFrame(frame);
    }

    raf = requestAnimationFrame(frame);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, [reverse, animationSpeed, dotSize, cellSize]);

  return (
    <div className="absolute inset-0 overflow-hidden bg-black">
      <canvas ref={canvasRef} className="h-full w-full" />
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,_transparent_0%,_rgba(0,0,0,0.6)_100%)]" />
      <div className="absolute inset-x-0 top-0 h-1/3 bg-gradient-to-b from-black to-transparent" />
    </div>
  );
}
