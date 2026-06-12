"use client";

import { clsx } from "clsx";

interface WaveformProps {
  active: boolean;
  paused?: boolean;
}

const bars = [18, 34, 24, 44, 30, 54, 26, 42, 22, 36, 18, 28];

export function Waveform({ active, paused = false }: WaveformProps) {
  return (
    <div
      aria-hidden="true"
      className="flex h-14 w-full items-center justify-center gap-1.5 rounded-full bg-white/80 px-5"
    >
      {bars.map((height, index) => (
        <span
          className={clsx(
            "block w-1.5 rounded-full bg-chat-green/80 transition-opacity",
            active && !paused && "wave-bar",
            (!active || paused) && "opacity-35"
          )}
          key={`${height}-${index}`}
          style={{
            animationDelay: `${index * 70}ms`,
            height
          }}
        />
      ))}
    </div>
  );
}
