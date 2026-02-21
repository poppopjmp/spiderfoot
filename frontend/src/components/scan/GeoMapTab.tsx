import { memo, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scanApi, type ScanEvent } from '../../lib/api';
import { MapPin } from 'lucide-react';
import { TableSkeleton, EmptyState } from '../ui';
import MiniStat from './MiniStat';
import { GEO_EVENT_TYPES, COUNTRY_COORDS, COUNTRY_NAME_TO_CODE, WORLD_MAP_IMAGE } from '../../lib/geo';

function GeoMapTab({ scanId }: { scanId: string }) {
  /* Fetch all geo-related event types */
  const geoQueries = GEO_EVENT_TYPES.map((t) => ({
    queryKey: ['scan-events-geo', scanId, t],
    queryFn: ({ signal }: { signal?: AbortSignal }) => scanApi.events(scanId, { event_type: t }, signal),
    enabled: !!scanId,
  }));

  const q0 = useQuery(geoQueries[0]);
  const q1 = useQuery(geoQueries[1]);
  const q2 = useQuery(geoQueries[2]);
  const q3 = useQuery(geoQueries[3]);

  const isLoading = q0.isLoading || q1.isLoading || q2.isLoading || q3.isLoading;

  /* Parse country data from GEOINFO events */
  const countryMap = useMemo(() => {
    const map = new Map<string, { count: number; city?: string; full?: string }>();
    const geoEvents: ScanEvent[] = q0.data?.events ?? [];
    const countryNameEvents: ScanEvent[] = q2.data?.events ?? [];

    geoEvents.forEach((e) => {
      const d = e.data?.trim();
      if (!d) return;
      if (d.length === 2 && /^[A-Z]{2}$/i.test(d)) {
        const code = d.toUpperCase();
        const prev = map.get(code) ?? { count: 0 };
        map.set(code, { ...prev, count: prev.count + 1 });
      } else {
        const parts = d.split(',').map((p: string) => p.trim());
        const lastPart = parts[parts.length - 1];
        if (lastPart && lastPart.length === 2 && /^[A-Z]{2}$/i.test(lastPart)) {
          const code = lastPart.toUpperCase();
          const prev = map.get(code) ?? { count: 0 };
          const city = parts[0];
          map.set(code, { count: prev.count + 1, city: prev.city ?? city, full: d });
        }
      }
    });

    countryNameEvents.forEach((e) => {
      const name = e.data?.trim().toLowerCase();
      if (!name) return;
      const code = COUNTRY_NAME_TO_CODE[name];
      if (code) {
        const prev = map.get(code) ?? { count: 0 };
        map.set(code, { ...prev, count: prev.count + 1 });
      }
    });

    return map;
  }, [q0.data, q2.data]);

  /* Parse coordinates */
  const coordinates = useMemo(() => {
    const coords: { lat: number; lon: number; label: string }[] = [];
    const coordEvents: ScanEvent[] = q1.data?.events ?? [];
    coordEvents.forEach((e) => {
      const parts = e.data?.split(',');
      if (parts?.length === 2) {
        const lat = parseFloat(parts[0]);
        const lon = parseFloat(parts[1]);
        if (!isNaN(lat) && !isNaN(lon)) {
          coords.push({ lat, lon, label: e.source_data || `${lat.toFixed(4)}, ${lon.toFixed(4)}` });
        }
      }
    });
    return coords;
  }, [q1.data]);

  /* Physical addresses */
  const addresses = useMemo(() => {
    return (q3.data?.events ?? []).map((e: ScanEvent) => e.data).filter(Boolean);
  }, [q3.data]);

  /* Sorted countries */
  const countryList = useMemo(() =>
    [...countryMap.entries()]
      .map(([code, info]) => ({ code, ...info }))
      .sort((a, b) => b.count - a.count),
    [countryMap],
  );

  const maxCount = countryList[0]?.count ?? 1;
  const totalGeoEvents = countryList.reduce((s, c) => s + c.count, 0) + coordinates.length + addresses.length;

  /* SVG World Map — viewport matches world-map.svg viewBox (2000×857) */
  const mapWidth = 2000;
  const mapHeight = 857;
  const LAT_TOP = 83.65;
  const LAT_BOT = -56.0;
  const projectLon = (lon: number) => ((lon + 180) / 360) * mapWidth;
  const projectLat = (lat: number) => ((LAT_TOP - lat) / (LAT_TOP - LAT_BOT)) * mapHeight;

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MiniStat label="Countries" value={countryList.length} />
        <MiniStat label="Geo Events" value={totalGeoEvents} />
        <MiniStat label="Coordinates" value={coordinates.length} />
        <MiniStat label="Addresses" value={addresses.length} />
      </div>

      {isLoading ? (
        <TableSkeleton rows={6} cols={3} />
      ) : totalGeoEvents === 0 ? (
        <EmptyState
          icon={MapPin}
          title="No geolocation data"
          description="Geolocation data will appear once the scan discovers location-related information."
        />
      ) : (
        <>
          {/* Map visualization */}
          <div className="card">
            <h3 className="text-sm font-semibold text-foreground mb-4">Geographic Distribution</h3>
            <div className="w-full overflow-x-auto">
              <svg viewBox={`0 0 ${mapWidth} ${mapHeight}`} role="img" aria-label="Geographic distribution of scan results" className="w-full min-w-[600px] rounded-lg overflow-hidden">
                <image href={WORLD_MAP_IMAGE} x={0} y={0} width={mapWidth} height={mapHeight} preserveAspectRatio="xMidYMid slice" opacity={0.55} />

                {/* Subtle grid overlay */}
                {[-60, -30, 0, 30, 60].map((lat) => (
                  <line key={`lat-${lat}`} x1={0} y1={projectLat(lat)} x2={mapWidth} y2={projectLat(lat)}
                    stroke="#ffffff" strokeWidth={0.8} opacity={0.08} />
                ))}
                {[-120, -60, 0, 60, 120].map((lon) => (
                  <line key={`lon-${lon}`} x1={projectLon(lon)} y1={0} x2={projectLon(lon)} y2={mapHeight}
                    stroke="#ffffff" strokeWidth={0.8} opacity={0.08} />
                ))}

                {/* Country markers */}
                {countryList.map((c) => {
                  const pos = COUNTRY_COORDS[c.code];
                  if (!pos) return null;
                  const [lat, lon] = pos;
                  const r = 10 + (c.count / maxCount) * 40;
                  return (
                    <g key={c.code}>
                      <circle cx={projectLon(lon)} cy={projectLat(lat)} r={r}
                        fill="#6366f1" fillOpacity={0.3} stroke="#6366f1" strokeWidth={2} />
                      <circle cx={projectLon(lon)} cy={projectLat(lat)} r={7}
                        fill="#818cf8" />
                      <text x={projectLon(lon)} y={projectLat(lat) - r - 8}
                        textAnchor="middle" fill="#c7d2fe" fontSize={24} fontFamily="Inter, system-ui, sans-serif">
                        {c.code} ({c.count})
                      </text>
                    </g>
                  );
                })}

                {/* Coordinate pins */}
                {coordinates.map((c, i) => (
                  <g key={`coord-${i}`}>
                    <circle cx={projectLon(c.lon)} cy={projectLat(c.lat)} r={12}
                      fill="#f59e0b" fillOpacity={0.5} stroke="#f59e0b" strokeWidth={3} />
                    <circle cx={projectLon(c.lon)} cy={projectLat(c.lat)} r={5}
                      fill="#fbbf24" />
                  </g>
                ))}
              </svg>
            </div>
            <div className="flex items-center gap-6 mt-3 text-xs text-dark-500">
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-indigo-500/50 border border-indigo-500 inline-block" /> Country (by event count)
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-3 h-3 rounded-full bg-amber-500/50 border border-amber-500 inline-block" /> Exact Coordinates
              </span>
            </div>
          </div>

          {/* Country distribution */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="card">
              <h3 className="text-sm font-semibold text-foreground mb-4">Country Distribution ({countryList.length})</h3>
              <div className="space-y-2.5 max-h-[400px] overflow-y-auto">
                {countryList.map((c, i) => {
                  const pct = maxCount > 0 ? (c.count / maxCount) * 100 : 0;
                  return (
                    <div key={c.code} className="flex items-center gap-3 animate-fade-in" style={{ animationDelay: `${i * 30}ms` }}>
                      <span className="text-sm font-mono text-dark-200 w-8">{c.code}</span>
                      <div className="flex-1">
                        <div className="progress-bar">
                          <div className="progress-fill animate-progress" style={{ width: `${pct}%`, backgroundColor: '#6366f1' }} />
                        </div>
                      </div>
                      <span className="text-xs text-dark-400 tabular-nums w-6 text-right">{c.count}</span>
                      {c.city && <span className="text-xs text-dark-600 truncate max-w-[120px]">{c.city}</span>}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="card">
              <h3 className="text-sm font-semibold text-foreground mb-4">Locations & Addresses</h3>
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {coordinates.length > 0 && (
                  <div>
                    <p className="text-xs text-dark-500 uppercase tracking-wider mb-2">Coordinates</p>
                    {coordinates.map((c, i) => (
                      <div key={i} className="flex items-center gap-2 py-1.5 border-b border-dark-700/30 last:border-0">
                        <MapPin className="h-3.5 w-3.5 text-amber-400 flex-shrink-0" />
                        <span className="text-xs font-mono text-dark-200">{c.lat.toFixed(4)}, {c.lon.toFixed(4)}</span>
                        <span className="text-xs text-dark-500 truncate flex-1">{c.label}</span>
                      </div>
                    ))}
                  </div>
                )}
                {addresses.length > 0 && (
                  <div>
                    <p className="text-xs text-dark-500 uppercase tracking-wider mb-2">Physical Addresses</p>
                    {addresses.map((addr: string, i: number) => (
                      <div key={i} className="flex items-start gap-2 py-1.5 border-b border-dark-700/30 last:border-0">
                        <MapPin className="h-3.5 w-3.5 text-green-400 flex-shrink-0 mt-0.5" />
                        <span className="text-xs text-dark-200">{addr}</span>
                      </div>
                    ))}
                  </div>
                )}
                {coordinates.length === 0 && addresses.length === 0 && (
                  <p className="text-dark-500 text-sm text-center py-8">No specific locations found</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default memo(GeoMapTab);
