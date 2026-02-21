import { useState, useRef, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { scanApi } from '../../lib/api';
import { Network, Download, Loader2 } from 'lucide-react';
import { EmptyState } from '../ui';

export default function GraphTab({ scanId }: { scanId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['scan-viz', scanId],
    queryFn: () => scanApi.viz(scanId),
  });

  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [graphReady, setGraphReady] = useState(false);

  const downloadGexf = async () => {
    try {
      const resp = await scanApi.exportEvents(scanId, { filetype: 'gexf' });
      const url = URL.createObjectURL(resp.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${scanId}.gexf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch { /* ignore */ }
  };

  const nodes = data?.nodes ?? [];
  const edges = data?.edges ?? [];

  /* Simple force-directed graph on canvas */
  useEffect(() => {
    if (!canvasRef.current || nodes.length === 0) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    canvas.width = canvas.offsetWidth * (window.devicePixelRatio || 1);
    canvas.height = canvas.offsetHeight * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    const w = canvas.offsetWidth;
    const h = canvas.offsetHeight;

    // Initialize node positions
    const nodeMap = new Map<string, { x: number; y: number; vx: number; vy: number; label: string; color: string }>();
    const typeColors: Record<string, string> = {
      'ROOT': '#22c55e', 'IP_ADDRESS': '#3b82f6', 'INTERNET_NAME': '#6366f1',
      'EMAILADDR': '#ec4899', 'DOMAIN_NAME': '#f59e0b', 'HUMAN_NAME': '#8b5cf6',
      'PHONE_NUMBER': '#06b6d4', 'ASN': '#ef4444',
    };
    nodes.forEach((n: { id: string; label?: string; type?: string }) => {
      nodeMap.set(n.id, {
        x: w / 2 + (Math.random() - 0.5) * w * 0.6,
        y: h / 2 + (Math.random() - 0.5) * h * 0.6,
        vx: 0, vy: 0,
        label: n.label || n.id.slice(0, 16),
        color: typeColors[n.type || ''] || '#64748b',
      });
    });

    const edgeList = edges.map((e: { source: string; target: string }) => ({
      src: nodeMap.get(e.source),
      tgt: nodeMap.get(e.target),
    })).filter((e: { src?: unknown; tgt?: unknown }) => e.src && e.tgt);

    let running = true;
    let frame = 0;
    let rafId = 0;
    const maxFrames = 200;

    function tick() {
      if (!running || !ctx) return;
      frame++;
      const alpha = Math.max(0.01, 1 - frame / maxFrames);

      // Repulsion (simplified Barnes-Hut)
      const allNodes = [...nodeMap.values()];
      for (let i = 0; i < allNodes.length; i++) {
        for (let j = i + 1; j < allNodes.length; j++) {
          const a = allNodes[i], b = allNodes[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          const d = Math.sqrt(dx * dx + dy * dy) || 1;
          const force = (150 / (d * d)) * alpha;
          dx *= force; dy *= force;
          a.vx -= dx; a.vy -= dy;
          b.vx += dx; b.vy += dy;
        }
      }

      // Attraction (edges)
      edgeList.forEach((e: { src: { x: number; y: number; vx: number; vy: number }; tgt: { x: number; y: number; vx: number; vy: number } }) => {
        let dx = e.tgt.x - e.src.x, dy = e.tgt.y - e.src.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (d - 80) * 0.005 * alpha;
        dx = (dx / d) * force; dy = (dy / d) * force;
        e.src.vx += dx; e.src.vy += dy;
        e.tgt.vx -= dx; e.tgt.vy -= dy;
      });

      // Center gravity
      allNodes.forEach((n) => {
        n.vx += (w / 2 - n.x) * 0.001 * alpha;
        n.vy += (h / 2 - n.y) * 0.001 * alpha;
        n.vx *= 0.85; n.vy *= 0.85;
        n.x = Math.max(20, Math.min(w - 20, n.x + n.vx));
        n.y = Math.max(20, Math.min(h - 20, n.y + n.vy));
      });

      // Draw
      ctx.clearRect(0, 0, w, h);

      // Edges
      ctx.globalAlpha = 0.15;
      ctx.strokeStyle = '#64748b';
      ctx.lineWidth = 0.5;
      edgeList.forEach((e: { src: { x: number; y: number }; tgt: { x: number; y: number } }) => {
        ctx.beginPath();
        ctx.moveTo(e.src.x, e.src.y);
        ctx.lineTo(e.tgt.x, e.tgt.y);
        ctx.stroke();
      });

      // Nodes
      ctx.globalAlpha = 1;
      allNodes.forEach((n) => {
        ctx.beginPath();
        ctx.arc(n.x, n.y, 4, 0, Math.PI * 2);
        ctx.fillStyle = n.color;
        ctx.fill();
      });

      // Labels (only for small graphs)
      if (allNodes.length <= 60) {
        ctx.font = '9px Inter, system-ui, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = '#94a3b8';
        allNodes.forEach((n) => {
          ctx.fillText(n.label.slice(0, 20), n.x, n.y + 14);
        });
      }

      if (frame < maxFrames) rafId = requestAnimationFrame(tick);
      else setGraphReady(true);
    }

    tick();
    return () => { running = false; cancelAnimationFrame(rafId); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length, edges.length]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-dark-400">
          {nodes.length} nodes · {edges.length} edges
          {graphReady && <span className="text-green-400 ml-2">● Layout complete</span>}
        </p>
        <button className="btn-secondary" onClick={downloadGexf}>
          <Download className="h-4 w-4" /> Download GEXF
        </button>
      </div>

      <div className="card p-0 overflow-hidden" style={{ minHeight: '500px' }}>
        {isLoading ? (
          <div className="flex items-center justify-center h-[500px]">
            <Loader2 className="h-8 w-8 text-dark-500 animate-spin" />
          </div>
        ) : nodes.length > 0 ? (
          <canvas
            ref={canvasRef}
            className="w-full h-[500px] cursor-move"
            style={{ background: '#0f172a' }}
          />
        ) : (
          <div className="flex items-center justify-center h-[500px]">
            <EmptyState
              icon={Network}
              title="No graph data"
              description="Graph data will be available once the scan produces results."
            />
          </div>
        )}
      </div>
    </div>
  );
}
