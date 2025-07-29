// src/components/MetricToggle.tsx
import { useFilters, Metric } from "@/store/useFilters";

const METRICS: Metric[] = ["pm1", "pm25", "pm10"];

export default function MetricToggle() {
  const { metrics, toggleMetric } = useFilters();
  return (
    <div className="flex gap-4">
      {METRICS.map((m) => (
        <label key={m} className="flex items-center gap-1">
          <input
            type="checkbox"
            checked={metrics.includes(m)}
            onChange={() => toggleMetric(m)}
          />
          <span className="capitalize">{m}</span>
        </label>
      ))}
    </div>
  );
}
