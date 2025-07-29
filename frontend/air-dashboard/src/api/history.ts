import { useQuery } from "@tanstack/react-query";
import { useFilters } from "@/store/useFilters";

export interface ReadingDTO {
  ts: number;
  device_id: string;
  pm1: number;
  pm25: number;
  pm10: number;
}

export const useHistory = () => {
  const { room, from, to, metrics, live } = useFilters();

  return useQuery({
    queryKey: ["history", room, from, to, metrics.sort().join(",")],
    queryFn: async (): Promise<ReadingDTO[]> => {
      const url = new URL("/history", import.meta.env.VITE_API_BASE);
      url.searchParams.set("room", room);
      if (from) url.searchParams.set("from", from);
      if (to) url.searchParams.set("to", to);
      url.searchParams.set("metrics", metrics.join(","));
      const res = await fetch(url.toString());
      if (!res.ok) throw new Error(res.statusText);
      return res.json();
    },
    refetchInterval: live ? 5000 : false,
    keepPreviousData: true,
  });
};
