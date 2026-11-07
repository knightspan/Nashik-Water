export type Colour = 'GREEN' | 'AMBER' | 'RED' | 'GREY';
export type Label =
  'Normal' | 'Natural change' | 'Contamination' | 'Sensor check' | 'Learning baseline';
export type Health = 'ok' | 'offline' | 'flatline' | 'out_of_range';
export type Band = 'excellent' | 'good' | 'poor' | 'very_poor' | 'unfit';
export type Param = 'ph' | 'tds' | 'turb' | 'temp' | 'wqi';

export interface Reading {
  ts: string;
  ph: number | null;
  tds: number | null;
  turb: number | null;
  temp: number | null;
  wqi: number | null;
  wqi_band: Band | null;
  label: Label;
  colour: Colour;
  confidence: number | null;
  health: Health;
  synthetic: boolean;
  latency_ms: number | null;
}

export interface Site {
  id: string;
  name_en: string;
  name_mr: string;
  kind: string;
  lat: number;
  lon: number;
  simulated: boolean;
  active: boolean;
  description_en: string;
  description_mr: string;
}

export interface Source extends Site {
  latest: Reading | null;
  stale: boolean;
  status_colour: Colour;
}

export interface SeriesPoint {
  ts: string;
  ph: number | null;
  tds: number | null;
  turb: number | null;
  temp: number | null;
  wqi: number | null;
  colour: Colour | null;
  n: number;
}

export interface Series {
  site_id: string;
  hours: number;
  resolution: 'raw' | '15min' | '1h';
  points: SeriesPoint[];
}

export interface ParamStats {
  min: number | null;
  max: number | null;
  mean: number | null;
  median: number | null;
}

export interface Stats {
  site_id: string;
  days: number;
  count: number;
  params: Record<Param, ParamStats>;
  wqi_bands: Record<Band, number>;
  colours: Record<Colour, number>;
}

export interface Alert {
  id: number;
  site_id: string;
  site_name_en: string;
  site_name_mr: string;
  ts: string;
  label: Label;
  confidence: number | null;
  wqi: number | null;
  acknowledged: boolean;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  note: string | null;
}

export interface Summary {
  colours: Record<Colour, number>;
  sites: number;
  stale_sites: number;
  active_alerts: number;
  last_update: string | null;
}

export interface Health_ {
  status: 'ok' | 'degraded';
  database: 'ok' | 'unreachable';
  version: string;
  time: string;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
}

export interface User {
  id: number;
  email: string;
  role: 'admin' | 'viewer';
  created_at: string;
  last_login_at: string | null;
}

export interface ApiKey {
  id: number;
  name: string;
  prefix: string;
  active: boolean;
  created_by: string | null;
  created_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
}

export interface AuditEntry {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  details: Record<string, unknown>;
  ip: string | null;
  ts: string;
}

export interface SiteIngestHealth {
  site_id: string;
  name_en: string;
  simulated: boolean;
  last_received_at: string | null;
  last_ts: string | null;
  messages_last_hour: number;
  hourly: number[];
}
