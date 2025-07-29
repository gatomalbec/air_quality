// src/components/CompositeChart.tsx
import { Line } from "react-chartjs-2";
import { Chart as ChartJS, LineElement, PointElement, Filler, CategoryScale, LinearScale, TimeScale } from "chart.js";
import 'chartjs-adapter-date-fns';
import { useHistory } from "@/api/history";
import { useFilters } from "@/store/useFilters";

ChartJS.register(LineElement, PointElement, Filler, CategoryScale, LinearScale, TimeScale);

const COLORS = { pm1: "#2563eb", pm25: "#059669", pm10: "#d97706" } as const;

export default function CompositeChart() {
  const { data = [] } = useHistory();
  const { metrics } = useFilters();

  /* transform */
  const labels = data.map(d => d.ts * 1000);      // ms epoch for time scale

  const datasets = (["pm1", "pm25", "pm10"] as const)
    .filter(m => metrics.includes(m))
    .map(m => ({
      label: m,
      data: data.map(d => d[m]),
      borderColor: COLORS[m],
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.25,
    }));

  const chartData = { labels, datasets };

  const opts: any = {
    maintainAspectRatio: false,
    scales: {
      x: { type: "time", time: { unit: "minute" } },
      y: { beginAtZero: true },
    },
    animation: false,
    plugins: { legend: { display: true } },
  };

  return (
    <div className="h-72 w-full">
      <Line data={chartData} options={opts} />
    </div>
  );
}
