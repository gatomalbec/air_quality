// src/components/MetricChart.tsx
import { useHistory } from "@/api/history";
import { Metric } from "@/store/useFilters";
import { useSize } from "@/hooks/useSize";

import { scaleTime, scaleLinear } from "@visx/scale";
import { LinePath } from "@visx/shape";
import { AxisBottom, AxisLeft } from "@visx/axis";
import dayjs from "dayjs";

const MARGIN = { top: 10, right: 20, bottom: 20, left: 40 };
const FALLBACK_W = 320;
const FALLBACK_H = 160;

interface Props {
  metric: Metric;
  color: string;
  width?: number;   // optional fixed size override
  height?: number;
}

export default function MetricChart({
  metric,
  color,
  width,
  height,
}: Props) {
  /* ───── container auto‑size ─────────────────────────────────── */
  const [ref, size] = useSize<HTMLDivElement>();
  const w = width ?? (size.w || FALLBACK_W);
  const h = height ?? (size.h || FALLBACK_H);

  /* ───── fetch and transform data ───────────────────────────── */
  const { data = [] } = useHistory();
  const points = data.map((d) => ({
    x: d.ts * 1000,          // ms
    y: d[metric],
  }));

  /* domains */
  const xDomain =
    points.length > 0
      ? [
          points[points.length - 1].x - 60 * 60 * 1000, // last hour
          points[points.length - 1].x,
        ]
      : [Date.now() - 60 * 60 * 1000, Date.now()];

  const yDomain =
    points.length > 0
      ? [0, Math.max(...points.map((p) => p.y)) * 1.1]
      : [0, 10];

  /* scales */
  const xScale = scaleTime({
    domain: xDomain,
    range: [MARGIN.left, w - MARGIN.right],
  });
  const yScale = scaleLinear({
    domain: yDomain,
    range: [h - MARGIN.bottom, MARGIN.top],
  });

  /* ───── render ─────────────────────────────────────────────── */
  return (
    <div ref={ref} className="w-full h-60">
      <svg width={w} height={h} className="bg-white border rounded">
        {/* axes */}
        <AxisBottom
          scale={xScale}
          top={h - MARGIN.bottom}
          stroke="#9ca3af"
          tickStroke="#9ca3af"
          tickFormat={(v) => dayjs(v as number).format("HH:mm")}
          tickLabelProps={{ fill: "#6b7280", fontSize: 11 }}
        />
        <AxisLeft
          scale={yScale}
          left={MARGIN.left}
          stroke="#9ca3af"
          tickStroke="#9ca3af"
          tickLabelProps={{ fill: "#6b7280", fontSize: 11 }}
        />

        {/* data or placeholder */}
        {points.length > 0 ? (
          <LinePath
            data={points}
            x={(p) => xScale(p.x)}
            y={(p) => yScale(p.y)}
            stroke={color}
            strokeWidth={2}
          />
        ) : (
          <text
            x={(w + MARGIN.left - MARGIN.right) / 2}
            y={(h + MARGIN.top - MARGIN.bottom) / 2}
            textAnchor="middle"
            fill="#9ca3af"
            fontSize={14}
          >
            No data
          </text>
        )}
      </svg>
    </div>
  );
}
