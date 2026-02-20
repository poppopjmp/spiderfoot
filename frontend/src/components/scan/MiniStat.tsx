/** Shared small stat card used by SummaryTab and GeoMapTab. */
export default function MiniStat({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="card-hover text-center py-4">
      <p className="text-xl font-bold text-foreground">{value}</p>
      <p className="text-xs text-dark-400 mt-1">{label}</p>
    </div>
  );
}
