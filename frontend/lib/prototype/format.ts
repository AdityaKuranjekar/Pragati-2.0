export const f2 = (v: number) => v.toFixed(2);
export const fmtTime = (iso: string) => {
  const d = new Date(iso);
  return isNaN(+d) ? iso : d.toLocaleString("en-IN", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};
