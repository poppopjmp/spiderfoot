/**
 * Shared geographic constants used by GeoMapTab and ReportTab.
 */

export const GEO_EVENT_TYPES = ['GEOINFO', 'PHYSICAL_COORDINATES', 'COUNTRY_NAME', 'PHYSICAL_ADDRESS'] as const;

/** Country code → approximate lat/lon for map positioning. */
export const COUNTRY_COORDS: Record<string, [number, number]> = {
  US: [37.0902, -95.7129], GB: [55.3781, -3.4360], DE: [51.1657, 10.4515], FR: [46.2276, 2.2137],
  CA: [56.1304, -106.3468], AU: [-25.2744, 133.7751], JP: [36.2048, 138.2529], CN: [35.8617, 104.1954],
  IN: [20.5937, 78.9629], BR: [-14.2350, -51.9253], RU: [61.5240, 105.3188], NL: [52.1326, 5.2913],
  SE: [60.1282, 18.6435], IT: [41.8719, 12.5674], ES: [40.4637, -3.7492], KR: [35.9078, 127.7669],
  SG: [1.3521, 103.8198], IE: [53.1424, -7.6921], CH: [46.8182, 8.2275], PL: [51.9194, 19.1451],
  NO: [60.4720, 8.4689], FI: [61.9241, 25.7482], DK: [56.2639, 9.5018], AT: [47.5162, 14.5501],
  BE: [50.5039, 4.4699], CZ: [49.8175, 15.4730], PT: [39.3999, -8.2245], MX: [23.6345, -102.5528],
  AR: [-38.4161, -63.6167], ZA: [-30.5595, 22.9375], IL: [31.0461, 34.8516], AE: [23.4241, 53.8478],
  TW: [23.6978, 120.9605], HK: [22.3193, 114.1694], MY: [4.2105, 101.9758], TH: [15.8700, 100.9925],
  PH: [12.8797, 121.7740], VN: [14.0583, 108.2772], ID: [-0.7893, 113.9213], NZ: [-40.9006, 174.8860],
  UA: [48.3794, 31.1656], RO: [45.9432, 24.9668], HU: [47.1625, 19.5033], BG: [42.7339, 25.4858],
  HR: [45.1000, 15.2000], SK: [48.6690, 19.6990], LT: [55.1694, 23.8813], LV: [56.8796, 24.6032],
  EE: [58.5953, 25.0136], GR: [39.0742, 21.8243], TR: [38.9637, 35.2433], EG: [26.8206, 30.8025],
  NG: [9.0820, 8.6753], KE: [0.0236, 37.9062], CO: [4.5709, -74.2973], CL: [-35.6751, -71.5430],
  PE: [-9.1900, -75.0152], VE: [6.4238, -66.5897],
};

/** Country name → 2-letter code mapping for COUNTRY_NAME events. */
export const COUNTRY_NAME_TO_CODE: Record<string, string> = {
  'united states': 'US', 'united kingdom': 'GB', 'germany': 'DE', 'france': 'FR',
  'canada': 'CA', 'australia': 'AU', 'japan': 'JP', 'china': 'CN', 'india': 'IN',
  'brazil': 'BR', 'russia': 'RU', 'netherlands': 'NL', 'sweden': 'SE', 'italy': 'IT',
  'spain': 'ES', 'south korea': 'KR', 'singapore': 'SG', 'ireland': 'IE',
  'switzerland': 'CH', 'poland': 'PL', 'norway': 'NO', 'finland': 'FI', 'denmark': 'DK',
  'austria': 'AT', 'belgium': 'BE', 'czech republic': 'CZ', 'czechia': 'CZ',
  'portugal': 'PT', 'mexico': 'MX', 'argentina': 'AR', 'south africa': 'ZA',
  'israel': 'IL', 'united arab emirates': 'AE', 'taiwan': 'TW', 'hong kong': 'HK',
  'malaysia': 'MY', 'thailand': 'TH', 'philippines': 'PH', 'vietnam': 'VN',
  'indonesia': 'ID', 'new zealand': 'NZ', 'ukraine': 'UA', 'romania': 'RO',
  'hungary': 'HU', 'bulgaria': 'BG', 'croatia': 'HR', 'turkey': 'TR', 'egypt': 'EG',
  'nigeria': 'NG', 'kenya': 'KE', 'colombia': 'CO', 'chile': 'CL', 'peru': 'PE',
};

/** World map SVG background (equirectangular projection, served from /public). */
export const WORLD_MAP_IMAGE = '/world-map.svg';
