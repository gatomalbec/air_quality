// src/store/useFilters.ts
import { create } from "zustand";

/* ---------------------------------------------------------------- *
 * Types
 * ---------------------------------------------------------------- */
export type Metric = "pm1" | "pm25" | "pm10";

interface Filters {
  /* state */
  room: string;
  metrics: Metric[];      // which series are currently shown
  from: string;           // ISO 8601 start
  to: string;             // ISO 8601 end
  live: boolean;          // polling on/off

  /* mutators */
  set: (patch: Partial<Filters>) => void;
  toggleMetric: (m: Metric) => void;
  toggleLive: () => void;
}

/* ---------------------------------------------------------------- *
 * Store
 * ---------------------------------------------------------------- */
export const useFilters = create<Filters>((set) => ({
  /* defaults ----------------------------------------------------- */
  room: "kitchen",
  metrics: ["pm1", "pm25", "pm10"],
  from: "",
  to: "",
  live: true,

  /* generic patch setter ---------------------------------------- */
  set: (patch) => set(patch),

  /* toggle a metric on/off -------------------------------------- */
  toggleMetric: (m) =>
    set((state) => ({
      metrics: state.metrics.includes(m)
        ? state.metrics.filter((x) => x !== m)
        : [...state.metrics, m],
    })),

  /* toggle live polling ----------------------------------------- */
  toggleLive: () => set((state) => ({ live: !state.live })),
}));
