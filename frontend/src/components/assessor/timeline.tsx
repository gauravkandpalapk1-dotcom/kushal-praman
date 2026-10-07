"use client";

import { motion } from "motion/react";
import { mmss, range } from "@/lib/format";
import type { Segment } from "@/lib/types";
import { cx } from "../ui";

export interface Highlight {
  start_s: number;
  end_s: number;
  label: string;
}

/** 0:00 ─── 5:00 ─── 10:00 bar with scene cuts, the AI-surfaced segment(s) and a playhead. Click to seek. */
export function Timeline({
  duration,
  segments,
  highlights,
  current,
  onSeek,
  animateHighlight = true,
}: {
  duration: number;
  segments: Segment[];
  highlights: Highlight[];
  current: number;
  onSeek: (t: number) => void;
  animateHighlight?: boolean;
}) {
  const d = Math.max(duration, 1);
  const pctOf = (t: number) => `${Math.min(100, Math.max(0, (t / d) * 100))}%`;
  const ticks = [0, d / 2, d];

  return (
    <div className="select-none">
      <div className="relative h-14 pt-7">
        {highlights.map((h, i) => (
          <motion.button
            key={`${h.start_s}-${i}`}
            initial={animateHighlight ? { opacity: 0, y: 6 } : false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.35 }}
            onClick={() => onSeek(h.start_s)}
            className="absolute top-0 -translate-x-2 rounded-full bg-amber-500 px-2.5 py-0.5 text-[0.72rem] font-bold text-navy-950 whitespace-nowrap shadow-lg shadow-amber-700/30"
            style={{ left: pctOf(h.start_s) }}
          >
            {h.label} {range(h.start_s, h.end_s)}
          </motion.button>
        ))}
        <div
          className="relative h-3 cursor-pointer rounded-full bg-navy-700"
          onClick={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            onSeek(((e.clientX - r.left) / r.width) * d);
          }}
          role="slider"
          aria-label="Recording timeline"
          aria-valuemin={0}
          aria-valuemax={Math.round(d)}
          aria-valuenow={Math.round(current)}
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "ArrowRight") onSeek(Math.min(d, current + 5));
            if (e.key === "ArrowLeft") onSeek(Math.max(0, current - 5));
          }}
        >
          <div className="absolute inset-y-0 left-0 rounded-full bg-navy-600" style={{ width: pctOf(current) }} />
          {segments.map((s) =>
            s.start_s > 0 ? <span key={s.id} className="absolute -top-1 h-5 w-px bg-navy-300/50" style={{ left: pctOf(s.start_s) }} title={`Scene cut ${mmss(s.start_s)}`} /> : null,
          )}
          {highlights.map((h, i) => (
            <motion.span
              key={i}
              initial={animateHighlight ? { scaleX: 0, opacity: 0 } : false}
              animate={{ scaleX: 1, opacity: 1 }}
              transition={{ duration: 0.5 }}
              className="absolute -top-1.5 h-6 origin-left rounded-sm bg-amber-500 ring-2 ring-amber-300/60 animate-pulse-ring"
              style={{ left: pctOf(h.start_s), width: `max(${((h.end_s - h.start_s) / d) * 100}%, 10px)` }}
            />
          ))}
          <span className="absolute -top-2 h-7 w-1 -translate-x-1/2 rounded bg-ink shadow" style={{ left: pctOf(current) }} />
        </div>
      </div>
      <div className="mt-1.5 flex justify-between text-[0.72rem] font-medium text-navy-300 tabular">
        {ticks.map((t, i) => (
          <span key={i}>{mmss(t)}</span>
        ))}
      </div>
    </div>
  );
}

/** Imperative helpers around a <video> element: seek, and play just one segment. */
export function playSegment(video: HTMLVideoElement | null, start: number, end: number) {
  if (!video) return;
  video.currentTime = start;
  void video.play().catch(() => {});
  const stopAt = () => {
    if (video.currentTime >= end) {
      video.pause();
      video.removeEventListener("timeupdate", stopAt);
    }
  };
  video.addEventListener("timeupdate", stopAt);
}

export function SegmentChip({ start, end, className }: { start: number; end: number; className?: string }) {
  return <span className={cx("rounded-md bg-amber-500 px-2 py-0.5 font-mono text-xs font-bold text-navy-950 tabular", className)}>{range(start, end)}</span>;
}
