import CompositeChart from "@/components/CompositeChart";
import MetricToggle from "@/components/MetricToggle";

export default function App() {
  return (
    <div className="p-4 space-y-4">
      <MetricToggle />
      <CompositeChart />
    </div>
  );
}
