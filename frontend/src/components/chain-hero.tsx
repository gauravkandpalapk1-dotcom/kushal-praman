"use client";

import { motion } from "motion/react";
import { ArrowRight } from "lucide-react";

/** The deck's core visual, rebuilt as UI: 10:00 video → surfaced segment → #17 → NOS → PC → score order. */
export function ChainHero({ caption = true }: { caption?: boolean }) {
  const start = 42 / 600;
  const width = 26 / 600;
  return (
    <div className="rounded-2xl bg-navy-950 p-5 sm:p-6 ring-1 ring-white/10 shadow-2xl shadow-navy-950/40">
      <div className="flex items-center gap-2 text-navy-300 text-sm">
        <span className="flex gap-1">
          <i className="size-2 rounded-full bg-navy-600" />
          <i className="size-2 rounded-full bg-navy-600" />
          <i className="size-2 rounded-full bg-navy-600" />
        </span>
        <span className="ml-1">Evidence workspace · Assistant Electrician</span>
      </div>
      <div className="mt-4 eyebrow text-cream-100">Practical demonstration · 10:00 video</div>

      <div className="relative mt-8 mb-2 h-2 rounded-full bg-navy-700">
        <motion.div
          initial={{ opacity: 0, scaleX: 0.3 }}
          animate={{ opacity: 1, scaleX: 1 }}
          transition={{ delay: 0.4, duration: 0.5 }}
          className="absolute -top-1.5 h-5 rounded-sm bg-amber-500 ring-2 ring-amber-300/50 origin-left"
          style={{ left: `${start * 100}%`, width: `max(${width * 100}%, 14px)` }}
        />
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          className="absolute -top-9 rounded-full bg-amber-500 px-3 py-1 text-xs font-bold text-navy-950 whitespace-nowrap"
          style={{ left: `calc(${start * 100}% + 18px)` }}
        >
          AI surfaced 00:42–01:08
        </motion.div>
      </div>
      <div className="flex justify-between text-[0.7rem] text-navy-400 tabular">
        <span>0:00</span>
        <span>5:00</span>
        <span>10:00</span>
      </div>

      <div className="mt-5 grid grid-cols-[1fr_auto_1fr_auto_1.15fr] items-center gap-1.5 sm:gap-2">
        <Node delay={1.0} k="Evidence" v="#17" />
        <Arrow delay={1.15} />
        <Node delay={1.25} k="NOS" v="ISC/N1002" />
        <Arrow delay={1.4} />
        <Node delay={1.5} k="Performance criterion" v="PC10" accent />
      </div>
      <div className="mt-2 grid grid-cols-[1fr_auto_1fr_auto_1fr] items-center gap-1.5 sm:gap-2">
        <Node delay={1.8} k="① Your score · first" v="3 / 4" light />
        <Arrow delay={1.95} />
        <Node delay={2.05} k="② AI · shown after" v="Supports" />
        <Arrow delay={2.2} />
        <Node delay={2.3} k="Final decision" v="3 / 4" />
      </div>
      {caption && (
        <p className="mt-4 text-[0.7rem] text-navy-400">
          Illustrative example from the demo: QP Assistant Electrician · NQR QG-03-IS-03883-2025-V2-IISSSC · NSQF 3 · NOS ISC/N1002, PC10 [4]
        </p>
      )}
    </div>
  );
}

function Node({ k, v, accent, light, delay }: { k: string; v: string; accent?: boolean; light?: boolean; delay: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.35 }}
      className={
        accent || light
          ? "rounded-lg bg-cream-50 px-2.5 py-2 sm:px-3 sm:py-2.5 text-navy-950"
          : "rounded-lg bg-navy-800 px-2.5 py-2 sm:px-3 sm:py-2.5 text-cream-50 ring-1 ring-white/5"
      }
    >
      <div className={`text-[0.58rem] sm:text-[0.62rem] font-bold uppercase tracking-wider leading-tight ${accent || light ? "text-navy-600" : "text-navy-300"}`}>{k}</div>
      <div className={`font-bold tabular leading-tight ${accent ? "text-xl sm:text-2xl" : "text-sm sm:text-lg"}`}>{v}</div>
    </motion.div>
  );
}

function Arrow({ delay }: { delay: number }) {
  return (
    <motion.span initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }} transition={{ delay }} className="text-amber-500">
      <ArrowRight className="size-4 sm:size-5" strokeWidth={3} />
    </motion.span>
  );
}
