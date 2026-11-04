"use client";

import { useEffect, useRef } from "react";
import type { EChartsOption, ECharts } from "echarts";

// One consistent ECharts theme: calm blue / teal / amber, never red.
export const PALETTE = ["#3b5bdb", "#0ca678", "#f08c00", "#7048e8", "#6b7389"];
const BASE: EChartsOption = {
  color: PALETTE,
  textStyle: { fontFamily: "'Inter Variable', 'Noto Sans Devanagari Variable', system-ui, sans-serif", color: "#4a5876" },
  grid: { left: 40, right: 16, top: 24, bottom: 32, containLabel: true },
  tooltip: { backgroundColor: "#fff", borderColor: "#e3e8f1", textStyle: { color: "#1f2430" } },
};

export function EChart({
  option,
  height = 260,
  label,
  onClick,
}: {
  option: EChartsOption;
  height?: number;
  label: string;
  onClick?: (p: { name?: string; dataIndex?: number; value?: unknown; data?: unknown }) => void;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<ECharts | null>(null);
  const optRef = useRef(option);
  optRef.current = option;
  const clickRef = useRef(onClick);
  clickRef.current = onClick;

  useEffect(() => {
    let ro: ResizeObserver | null = null;
    let dead = false;
    import("echarts").then((ec) => {
      if (dead || !el.current) return;
      chart.current = ec.init(el.current);
      chart.current.on("click", (p) => clickRef.current?.(p as never));
      ro = new ResizeObserver(() => chart.current?.resize());
      ro.observe(el.current);
      chart.current.setOption({ ...BASE, ...optRef.current, animation: !matchMedia("(prefers-reduced-motion: reduce)").matches }, true);
    });
    return () => {
      dead = true;
      ro?.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    chart.current?.setOption({ ...BASE, ...option }, true);
  }, [option]);

  return <div ref={el} role="img" aria-label={label} style={{ height }} className="w-full" />;
}
