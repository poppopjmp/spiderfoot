import { memo, useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { safeSetItem } from '../../lib/safeStorage';
import {
  scanApi, agentsApi, formatDuration,
  type Scan, type ScanEvent, type ScanCorrelation, type EventSummaryDetail,
} from '../../lib/api';
import {
  Brain, Edit3, Save, Sparkles, Loader2, FileText,
  AlertTriangle, BarChart3, Shield, MapPin, Download,
} from 'lucide-react';
import { DropdownMenu, DropdownItem, EmptyState } from '../ui';
import { sanitizeHTML } from '../../lib/sanitize';
import { COUNTRY_NAME_TO_CODE } from '../../lib/geo';

/* ── Helpers ──────────────────────────────────────────────── */

/** Escape a string for safe interpolation into an HTML template literal. */
function escapeHTML(s: string): string {
  return s.replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]!),
  );
}

function riskBadgeText(risk: string): string {
  const r = risk.toLowerCase();
  if (r === 'critical') return '🔴 CRITICAL';
  if (r === 'high') return '🟠 HIGH';
  if (r === 'medium') return '🟡 MEDIUM';
  if (r === 'low') return '🟢 LOW';
  return 'ℹ️ INFO';
}

/**
 * Convert the agent report API response into clean Markdown.
 */
function extractReportMarkdown(resp: Record<string, unknown>, target: string): string {
  const outer = resp ?? {};
  let reportData: Record<string, unknown> = (outer.data ?? outer) as Record<string, unknown>;

  if (typeof reportData.raw_report === 'string') {
    let raw = reportData.raw_report as string;
    raw = raw.replace(/^```(?:json)?\s*\n?/i, '').replace(/\n?```\s*$/i, '').trim();
    try {
      reportData = JSON.parse(raw);
    } catch {
      return raw;
    }
  }

  if (typeof reportData === 'string') return reportData;
  const keys = Object.keys(reportData);
  if (keys.length === 0) return '*No report data available.*';

  const hasStructured = ['title', 'executive_summary', 'key_findings', 'risk_rating'].some(k => k in reportData);
  if (!hasStructured) {
    const textField = (reportData.report ?? reportData.content ?? reportData.markdown ?? reportData.text) as string | undefined;
    if (typeof textField === 'string') return textField;
    return '```json\n' + JSON.stringify(reportData, null, 2) + '\n```';
  }

  const lines: string[] = [];
  const title = (reportData.title as string) || `OSINT Report — ${target}`;
  const riskRating = (reportData.risk_rating as string) || 'info';

  lines.push(`# ${title}`, '', `**Risk Rating:** ${riskBadgeText(riskRating)}`, `**Generated:** ${new Date().toLocaleString()}`, '', '---', '');

  if (reportData.executive_summary) {
    lines.push('## Executive Summary', '', reportData.executive_summary as string, '');
  }

  const findings = reportData.key_findings as Array<Record<string, string>> | undefined;
  if (findings?.length) {
    lines.push('## Key Findings', '');
    findings.forEach((f, i) => {
      const sev = f.severity ?? 'info';
      lines.push(`### ${i + 1}. ${f.title ?? 'Finding'} [${sev.toUpperCase()}]`, '');
      if (f.description) lines.push(f.description, '');
      if (f.evidence) lines.push(`> **Evidence:** ${f.evidence}`, '');
      if (f.recommendation) lines.push(`**Recommendation:** ${f.recommendation}`, '');
    });
  }

  const surface = reportData.attack_surface_summary as Record<string, unknown> | undefined;
  if (surface) {
    lines.push('## Attack Surface Summary', '', '| Metric | Count |', '|--------|------:|');
    if (surface.domains != null) lines.push(`| Domains | ${surface.domains} |`);
    if (surface.hosts != null) lines.push(`| Hosts | ${surface.hosts} |`);
    if (surface.emails != null) lines.push(`| Emails | ${surface.emails} |`);
    if (surface.open_ports != null) lines.push(`| Open Ports | ${surface.open_ports} |`);
    const techs = surface.technologies as string[] | undefined;
    if (techs?.length) lines.push(`| Technologies | ${techs.join(', ')} |`);
    const exposed = surface.exposed_services as string[] | undefined;
    if (exposed?.length) lines.push(`| Exposed Services | ${exposed.join(', ')} |`);
    lines.push('');
  }

  const geo = reportData.geographic_intelligence as Record<string, unknown> | undefined;
  if (geo) {
    lines.push('## Geographic Intelligence', '');
    if (geo.summary) lines.push(geo.summary as string, '');
    const geoCountries = geo.countries as Array<Record<string, unknown>> | undefined;
    if (geoCountries?.length) {
      lines.push('| Country | Code | Events |', '|---------|------|-------:|');
      geoCountries.forEach((c) => lines.push(`| ${c.name ?? ''} | ${c.code ?? ''} | ${c.count ?? 0} |`));
      lines.push('');
    }
    const geoCoords = geo.coordinates as Array<Record<string, unknown>> | undefined;
    if (geoCoords?.length) {
      lines.push('**Geo-located Endpoints:**', '');
      geoCoords.forEach((c) => lines.push(`- (${c.lat}, ${c.lon}) — ${c.label ?? ''}`));
      lines.push('');
    }
    const geoAddresses = geo.addresses as string[] | undefined;
    if (geoAddresses?.length) {
      lines.push('**Physical Addresses:**', '');
      geoAddresses.forEach((a) => lines.push(`- ${a}`));
      lines.push('');
    }
  }

  if (reportData.threat_assessment) {
    lines.push('## Threat Assessment', '', reportData.threat_assessment as string, '');
  }

  const recs = reportData.recommendations as Array<Record<string, string>> | undefined;
  if (recs?.length) {
    lines.push('## Recommendations', '');
    recs.forEach((r) => {
      const prio = r.priority ?? 'general';
      lines.push(`- **[${prio.toUpperCase().replace('_', ' ')}]** ${r.action}`);
      if (r.rationale) lines.push(`  *${r.rationale}*`);
    });
    lines.push('');
  }

  if (reportData.methodology) {
    lines.push('## Methodology', '', reportData.methodology as string, '');
  }

  const tags = reportData.tags as string[] | undefined;
  if (tags?.length) {
    lines.push('---', '', `**Tags:** ${tags.map(t => `\`${t}\``).join(' ')}`, '');
  }

  lines.push('---', '*Report generated by SpiderFoot AI Threat Intel Analyzer*');
  return lines.join('\n');
}

/* ── Component ────────────────────────────────────────────── */

function ReportTab({ scanId, scan }: { scanId: string; scan?: Scan }) {
  const [reportContent, setReportContent] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const editorRef = useRef<HTMLTextAreaElement>(null);

  const storageKey = `sf_report_${scanId}`;
  useEffect(() => {
    const saved = localStorage.getItem(storageKey);
    if (saved) setReportContent(saved);
  }, [storageKey]);

  const { data: summaryData } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => scanApi.summary(scanId),
    enabled: !!scanId,
  });

  const { data: corrData } = useQuery({
    queryKey: ['scan-correlations', scanId],
    queryFn: () => scanApi.correlations(scanId),
    enabled: !!scanId,
  });

  const { data: geoInfoData } = useQuery({
    queryKey: ['scan-events-geo-report', scanId, 'GEOINFO'],
    queryFn: () => scanApi.events(scanId, { event_type: 'GEOINFO' }),
    enabled: !!scanId,
  });
  const { data: geoCoordsData } = useQuery({
    queryKey: ['scan-events-geo-report', scanId, 'PHYSICAL_COORDINATES'],
    queryFn: () => scanApi.events(scanId, { event_type: 'PHYSICAL_COORDINATES' }),
    enabled: !!scanId,
  });
  const { data: geoCountryData } = useQuery({
    queryKey: ['scan-events-geo-report', scanId, 'COUNTRY_NAME'],
    queryFn: () => scanApi.events(scanId, { event_type: 'COUNTRY_NAME' }),
    enabled: !!scanId,
  });
  const { data: geoAddrData } = useQuery({
    queryKey: ['scan-events-geo-report', scanId, 'PHYSICAL_ADDRESS'],
    queryFn: () => scanApi.events(scanId, { event_type: 'PHYSICAL_ADDRESS' }),
    enabled: !!scanId,
  });

  const geoPayload = useMemo(() => {
    const countryMap = new Map<string, { count: number; name: string }>();

    (geoInfoData?.events ?? []).forEach((e: ScanEvent) => {
      const d = e.data?.trim();
      if (!d) return;
      if (d.length === 2 && /^[A-Z]{2}$/i.test(d)) {
        const code = d.toUpperCase();
        const prev = countryMap.get(code) ?? { count: 0, name: code };
        countryMap.set(code, { count: prev.count + 1, name: prev.name });
      } else {
        const parts = d.split(',').map((p: string) => p.trim());
        const lastPart = parts[parts.length - 1];
        if (lastPart?.length === 2 && /^[A-Z]{2}$/i.test(lastPart)) {
          const code = lastPart.toUpperCase();
          const prev = countryMap.get(code) ?? { count: 0, name: code };
          countryMap.set(code, { count: prev.count + 1, name: prev.name });
        }
      }
    });

    (geoCountryData?.events ?? []).forEach((e: ScanEvent) => {
      const name = e.data?.trim().toLowerCase();
      if (!name) return;
      const code = COUNTRY_NAME_TO_CODE[name];
      if (code) {
        const prev = countryMap.get(code) ?? { count: 0, name: '' };
        countryMap.set(code, { count: prev.count + 1, name: e.data!.trim() });
      }
    });

    const countries = [...countryMap.entries()].map(([code, info]) => ({
      code, name: info.name, count: info.count,
    })).sort((a, b) => b.count - a.count);

    const coordinates: { lat: number; lon: number; label: string }[] = [];
    (geoCoordsData?.events ?? []).forEach((e: ScanEvent) => {
      const parts = e.data?.split(',');
      if (parts?.length === 2) {
        const lat = parseFloat(parts[0]);
        const lon = parseFloat(parts[1]);
        if (!isNaN(lat) && !isNaN(lon)) {
          coordinates.push({ lat, lon, label: e.source_data || `${lat.toFixed(4)}, ${lon.toFixed(4)}` });
        }
      }
    });

    const addresses = (geoAddrData?.events ?? []).map((e: ScanEvent) => e.data).filter(Boolean) as string[];

    return { countries, coordinates, addresses };
  }, [geoInfoData, geoCoordsData, geoCountryData, geoAddrData]);

  const generateMut = useMutation({
    mutationFn: async () => {
      const details = summaryData?.details ?? [];
      const correlations = corrData?.correlations ?? [];
      const findings = details.slice(0, 20).map((d: EventSummaryDetail) => ({
        type: d.key, description: d.description, total: d.total, unique: d.unique_total,
      }));

      return agentsApi.report({
        scan_id: scanId,
        target: scan?.target ?? '',
        scan_name: scan?.name ?? '',
        findings,
        correlations: correlations.map((c: ScanCorrelation) => ({
          rule_id: c.rule_id, rule_name: c.rule_name, risk: c.rule_risk,
          description: c.rule_descr, event_count: c.event_count,
        })),
        stats: {
          total_events: details.reduce((s: number, d: EventSummaryDetail) => s + d.total, 0),
          total_types: summaryData?.total_types ?? 0,
          scan_status: scan?.status,
          duration: formatDuration(scan?.started ?? 0, scan?.ended ?? 0),
        },
        geo_data: geoPayload,
      });
    },
    onSuccess: (data) => {
      const md = extractReportMarkdown(data, scan?.target ?? '');
      setReportContent(md);
      safeSetItem(storageKey, md);
    },
    onError: (err: Error) => {
      console.error('Failed to generate report:', err);
    },
  });

  const generateClientReport = useCallback(() => {
    const details = summaryData?.details ?? [];
    const correlations: ScanCorrelation[] = corrData?.correlations ?? [];
    const totalEvents = details.reduce((s: number, d: EventSummaryDetail) => s + d.total, 0);

    const reportTitle = scan?.name || 'Threat Intelligence Report';
    const lines: string[] = [
      `# ${reportTitle}`, '',
      `**Target:** ${scan?.target ?? 'Unknown'}`,
      `**Scan ID:** \`${scanId}\``,
      `**Status:** ${scan?.status ?? 'Unknown'}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      `**Duration:** ${formatDuration(scan?.started ?? 0, scan?.ended ?? 0)}`,
      '', '---', '',
      '## Executive Summary', '',
      `This report summarizes the findings from the OSINT scan of **${scan?.target}**.`,
      `The scan discovered **${totalEvents.toLocaleString()}** data points across **${details.length}** different types.`,
      correlations.length > 0
        ? `**${correlations.length}** correlation rules were triggered, indicating potential security insights.`
        : 'No correlation rules were triggered.',
      '', '## Data Discovery', '',
      '| Type | Total | Unique |', '|------|------:|-------:|',
    ];

    const sorted = [...details].sort((a, b) => b.total - a.total);
    sorted.slice(0, 20).forEach((d) => {
      lines.push(`| ${d.description || d.key} | ${d.total} | ${d.unique_total} |`);
    });
    if (sorted.length > 20) lines.push(`| *(${sorted.length - 20} more types)* | | |`);

    if (correlations.length > 0) {
      lines.push('', '## Correlation Findings', '');
      const bySeverity: Record<string, ScanCorrelation[]> = {};
      correlations.forEach((c) => {
        const k = c.rule_risk || 'info';
        (bySeverity[k] ??= []).push(c);
      });
      ['critical', 'high', 'medium', 'low', 'info'].forEach((sev) => {
        const list = bySeverity[sev];
        if (!list?.length) return;
        lines.push(`### ${sev.charAt(0).toUpperCase() + sev.slice(1)} Severity`, '');
        list.forEach((c) => lines.push(`- **${c.rule_name}** — ${c.rule_descr} *(${c.event_count} events)*`));
        lines.push('');
      });
    }

    if (geoPayload.countries.length || geoPayload.coordinates.length || geoPayload.addresses.length) {
      lines.push('## Geographic Intelligence', '');
      if (geoPayload.countries.length) {
        lines.push('| Country | Code | Events |', '|---------|------|-------:|');
        geoPayload.countries.forEach((c) => lines.push(`| ${c.name} | ${c.code} | ${c.count} |`));
        lines.push('');
      }
      if (geoPayload.coordinates.length) {
        lines.push('**Geo-located Endpoints:**', '');
        geoPayload.coordinates.slice(0, 30).forEach((c) => lines.push(`- (${c.lat}, ${c.lon}) — ${c.label}`));
        lines.push('');
      }
      if (geoPayload.addresses.length) {
        lines.push('**Physical Addresses:**', '');
        geoPayload.addresses.slice(0, 20).forEach((a) => lines.push(`- ${a}`));
        lines.push('');
      }
    }

    lines.push(
      '## Recommendations', '',
      '> *Edit this section to add your analysis and recommendations.*', '',
      '1. Review high-risk correlation findings above.',
      '2. Investigate exposed services and potential data leaks.',
      '3. Validate discovered credentials and access paths.',
      '', '---', '*Report generated by SpiderFoot AI Threat Intel Analyzer*',
    );

    const md = lines.join('\n');
    setReportContent(md);
    safeSetItem(storageKey, md);
  }, [summaryData, corrData, scan, scanId, storageKey, geoPayload]);

  const startEditing = () => {
    setEditContent(reportContent);
    setIsEditing(true);
    setTimeout(() => editorRef.current?.focus(), 50);
  };

  const saveEdit = () => {
    setReportContent(editContent);
    safeSetItem(storageKey, editContent);
    setIsEditing(false);
  };

  const cancelEdit = () => {
    setIsEditing(false);
  };

  /* Simple Markdown renderer */
  const renderMarkdown = (md: string) => {
    const lines = md.split('\n');
    const html: string[] = [];
    let inTable = false;
    let inBlockquote = false;
    let inList = false;
    let inCodeBlock = false;

    lines.forEach((line) => {
      if (line.trim().startsWith('```')) {
        if (inCodeBlock) { html.push('</code></pre>'); inCodeBlock = false; }
        else { inCodeBlock = true; html.push('<pre class="bg-dark-900 border border-dark-700/50 rounded-lg p-4 my-3 overflow-x-auto"><code class="text-xs font-mono text-dark-300">'); }
        return;
      }
      if (inCodeBlock) {
        const escaped = line.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html.push(escaped);
        return;
      }

      if (/^---+$/.test(line.trim())) {
        if (inList) { html.push('</ul>'); inList = false; }
        if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
        html.push('<hr class="border-dark-700/50 my-6" />');
        return;
      }

      const hMatch = line.match(/^(#{1,6})\s+(.*)/);
      if (hMatch) {
        if (inList) { html.push('</ul>'); inList = false; }
        if (inBlockquote) { html.push('</blockquote>'); inBlockquote = false; }
        const level = hMatch[1].length;
        const sizes: Record<number, string> = {
          1: 'text-2xl font-bold text-foreground mt-6 mb-3 pb-2 border-b border-dark-700/40',
          2: 'text-xl font-bold text-foreground mt-5 mb-2',
          3: 'text-lg font-semibold text-dark-100 mt-4 mb-2',
          4: 'text-base font-semibold text-dark-200 mt-3 mb-1',
          5: 'text-sm font-semibold text-dark-300 mt-2 mb-1',
          6: 'text-xs font-semibold text-dark-400 mt-2 mb-1',
        };
        html.push(`<h${level} class="${sizes[level]}">${inlineFormat(hMatch[2])}</h${level}>`);
        return;
      }

      if (line.trim().startsWith('|')) {
        if (!inTable) { html.push('<div class="overflow-x-auto my-3"><table class="w-full text-sm border border-dark-700/40 rounded-lg overflow-hidden"><tbody>'); inTable = true; }
        if (/^\|[-:|\s]+\|$/.test(line.trim())) return;
        const cells = line.split('|').filter((c) => c.trim() !== '');
        const isHeader = !html.some((l) => l.includes('<tr'));
        const rowClass = isHeader ? 'bg-dark-800/60' : 'hover:bg-dark-800/30 transition-colors';
        html.push(`<tr class="border-b border-dark-700/30 ${rowClass}">`);
        cells.forEach((cell) => {
          const tag = isHeader ? 'th' : 'td';
          const cls = isHeader ? 'px-4 py-2.5 text-left text-xs font-semibold text-dark-300 uppercase tracking-wider' : 'px-4 py-2 text-dark-300';
          const align = cell.trim().match(/^\d/) ? ' text-right' : '';
          html.push(`<${tag} class="${cls}${align}">${inlineFormat(cell.trim())}</${tag}>`);
        });
        html.push('</tr>');
        return;
      } else if (inTable) {
        html.push('</tbody></table></div>');
        inTable = false;
      }

      if (line.trim().startsWith('>')) {
        if (!inBlockquote) { html.push('<blockquote class="border-l-3 border-spider-500 pl-4 py-2 my-3 bg-dark-800/30 rounded-r-lg">'); inBlockquote = true; }
        html.push(`<p class="text-sm text-dark-300">${inlineFormat(line.replace(/^>\s*/, ''))}</p>`);
        return;
      } else if (inBlockquote) {
        html.push('</blockquote>');
        inBlockquote = false;
      }

      const liMatch = line.match(/^(\s*)(\d+\.|[-*])\s+(.*)/);
      if (liMatch) {
        const isOrdered = /\d+\./.test(liMatch[2]);
        if (!inList) {
          const tag = isOrdered ? 'ol' : 'ul';
          const listClass = isOrdered ? 'list-decimal' : 'list-disc';
          html.push(`<${tag} class="${listClass} list-inside space-y-1.5 my-3 text-sm text-dark-300 pl-2">`);
          inList = true;
        }
        html.push(`<li class="leading-relaxed">${inlineFormat(liMatch[3])}</li>`);
        return;
      } else if (inList && line.trim() === '') {
        html.push('</ul>');
        inList = false;
      }

      if (line.trim() === '') {
        html.push('<div class="h-3"></div>');
        return;
      }

      html.push(`<p class="text-sm text-dark-300 leading-relaxed my-1">${inlineFormat(line)}</p>`);
    });

    if (inCodeBlock) html.push('</code></pre>');
    if (inTable) html.push('</tbody></table></div>');
    if (inList) html.push('</ul>');
    if (inBlockquote) html.push('</blockquote>');

    return html.join('\n');
  };

  const inlineFormat = (text: string): string => {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-foreground font-semibold">$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/`(.+?)`/g, '<code class="bg-dark-700 px-1 py-0.5 rounded text-spider-400 text-xs font-mono">$1</code>');
  };

  const exportMarkdown = () => {
    if (!reportContent) return;
    const blob = new Blob([reportContent], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${scan?.name || scanId}-report.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const exportPDF = () => {
    if (!reportContent) return;
    const html = sanitizeHTML(renderMarkdown(reportContent) ?? '');
    const printWindow = window.open('', '_blank');
    if (!printWindow) return;
    printWindow.document.write(`<!DOCTYPE html>
<html><head><title>${escapeHTML(scan?.name || scanId)} - Report</title>
<style>
  body { font-family: system-ui, -apple-system, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; }
  h1 { font-size: 24px; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }
  h2 { font-size: 20px; margin-top: 24px; color: #312e81; }
  h3 { font-size: 16px; margin-top: 16px; }
  table { width: 100%; border-collapse: collapse; margin: 12px 0; }
  th, td { padding: 8px 12px; border: 1px solid #ddd; text-align: left; font-size: 13px; }
  th { background: #f0f0f5; font-weight: 600; }
  code { background: #f5f5f5; padding: 2px 6px; border-radius: 3px; font-size: 13px; }
  pre { background: #f5f5f5; padding: 12px; border-radius: 6px; overflow-x: auto; }
  blockquote { border-left: 3px solid #6366f1; padding-left: 12px; margin: 12px 0; color: #555; }
  ul, ol { padding-left: 24px; }
  li { margin: 4px 0; }
  hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
  strong { font-weight: 600; }
  .meta { color: #666; font-size: 12px; margin-bottom: 24px; }
  @media print { body { margin: 20px; } }
</style></head><body>
<div class="meta">Generated: ${escapeHTML(new Date().toLocaleString())} | Target: ${escapeHTML(scan?.target ?? '')} | Scan ID: ${escapeHTML(scanId)}</div>
${html}
</body></html>`);
    printWindow.document.close();
    setTimeout(() => { printWindow.print(); }, 500);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">
          {reportContent ? 'AI-generated threat intelligence report' : 'Generate a comprehensive threat report'}
        </p>
        <div className="flex items-center gap-2">
          {reportContent && !isEditing && (
            <>
              <DropdownMenu trigger={<button className="btn-secondary"><Download className="h-4 w-4" /> Export</button>}>
                <DropdownItem icon={FileText} onClick={exportMarkdown}>Markdown (.md)</DropdownItem>
                <DropdownItem icon={FileText} onClick={exportPDF}>PDF (Print)</DropdownItem>
              </DropdownMenu>
              <button className="btn-secondary" onClick={startEditing}>
                <Edit3 className="h-4 w-4" /> Edit
              </button>
            </>
          )}
          {isEditing && (
            <>
              <button className="btn-secondary" onClick={cancelEdit}>Cancel</button>
              <button className="btn-primary" onClick={saveEdit}>
                <Save className="h-4 w-4" /> Save
              </button>
            </>
          )}
          <button
            className="btn-primary"
            onClick={() => generateMut.mutate()}
            disabled={generateMut.isPending}
          >
            {generateMut.isPending ? (
              <><Loader2 className="h-4 w-4 animate-spin" /> Generating...</>
            ) : (
              <><Sparkles className="h-4 w-4" /> Generate AI Report</>
            )}
          </button>
          <button className="btn-secondary" onClick={generateClientReport}>
            <FileText className="h-4 w-4" /> Quick Report
          </button>
        </div>
      </div>

      {generateMut.isError && (
        <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/10 border border-red-800/30 rounded-lg px-4 py-2">
          <AlertTriangle className="h-4 w-4" />
          Report generation failed. Try 'Quick Report' for a client-side summary.
        </div>
      )}

      {/* Report stats */}
      {reportContent && !isEditing && (
        <div className="flex gap-4 flex-wrap">
          {(() => {
            const headings = (reportContent.match(/^#{1,3}\s+.+/gm) || []).length;
            const tables = (reportContent.match(/^\|/gm) || []).length;
            const words = reportContent.split(/\s+/).length;
            return (
              <>
                <span className="badge badge-info"><BarChart3 className="h-3 w-3" /> {words} words</span>
                <span className="badge badge-info"><Brain className="h-3 w-3" /> {headings} sections</span>
                {tables > 0 && <span className="badge badge-info"><Shield className="h-3 w-3" /> {tables} table rows</span>}
                {reportContent.includes('Geographic Intelligence') && (
                  <span className="badge badge-info"><MapPin className="h-3 w-3" /> Geo included</span>
                )}
              </>
            );
          })()}
        </div>
      )}

      {/* Editor */}
      {isEditing ? (
        <div className="card p-0 overflow-hidden">
          <div className="bg-dark-800/50 border-b border-dark-700/50 px-4 py-2 text-xs text-dark-400 flex items-center gap-2">
            <Edit3 className="h-3.5 w-3.5" /> Editing Markdown — Save or Cancel when done
          </div>
          <textarea
            ref={editorRef}
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="w-full bg-dark-900 text-dark-200 font-mono text-xs p-4 focus:outline-none resize-y"
            style={{ minHeight: '500px' }}
            spellCheck={false}
          />
        </div>
      ) : reportContent ? (
        <div className="card p-6 lg:p-8">
          <div
            className="markdown-report max-w-none"
            dangerouslySetInnerHTML={{ __html: sanitizeHTML(renderMarkdown(reportContent) ?? '') }}
          />
        </div>
      ) : (
        <EmptyState
          icon={Brain}
          title="No report generated"
          description="Click 'Generate AI Report' to create a comprehensive threat intelligence report based on the scan data, or 'Quick Report' for a client-side summary."
          action={
            <div className="flex gap-2">
              <button className="btn-primary" onClick={() => generateMut.mutate()} disabled={generateMut.isPending}>
                <Sparkles className="h-4 w-4" /> Generate AI Report
              </button>
              <button className="btn-secondary" onClick={generateClientReport}>
                <FileText className="h-4 w-4" /> Quick Report
              </button>
            </div>
          }
        />
      )}
    </div>
  );
}

export default memo(ReportTab);
