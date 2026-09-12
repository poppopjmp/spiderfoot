import { useState, useRef, useEffect, useCallback } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { agentsApi, reportsApi, type Workspace } from '../../lib/api';
import MarkdownRenderer from '../MarkdownRenderer';
import { safeSetItem, safeRemoveItem } from '../../lib/safeStorage';
import { ConfirmDialog } from '../ui';
import { Brain, Edit3, Save, Loader2, AlertTriangle, Sparkles, FileText, Trash2 } from 'lucide-react';

interface WorkspaceReportCardProps {
  workspaceId: string;
  workspace?: Workspace;
  summary?: Record<string, unknown>;
  scanIds?: string[];
}

export default function WorkspaceReportCard({ workspaceId, workspace, summary, scanIds }: WorkspaceReportCardProps) {
  const [reportContent, setReportContent] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [editContent, setEditContent] = useState('');
  const [serverReportId, setServerReportId] = useState<string | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const queryClient = useQueryClient();

  const storageKey = `sf_ws_report_${workspaceId}`;

  // Same fix as ReportTab.tsx (PR #393, 2026-09-12): this was
  // localStorage-only, invisible from any other browser/device. Checks
  // the server (keyed by workspace_id, not by a guessed-at scan id) and
  // only falls back to localStorage when the server has nothing —
  // localStorage still wins when already present so an unsynced local
  // edit is never silently overwritten.
  const { data: storedReports } = useQuery({
    queryKey: ['stored-reports-workspace', workspaceId],
    queryFn: ({ signal }) => reportsApi.listByWorkspace(workspaceId, 1, signal),
    enabled: !!workspaceId,
    retry: false,
  });

  useEffect(() => {
    const serverReport = storedReports?.[0];
    setServerReportId(serverReport?.report_id ?? null);

    const saved = localStorage.getItem(storageKey);
    if (saved) {
      setReportContent(saved);
      return;
    }
    setReportContent('');
    if (!serverReport) return;
    reportsApi.get(serverReport.report_id)
      .then((full) => {
        const content = full.sections?.[0]?.content ?? '';
        if (content) {
          setReportContent(content);
          safeSetItem(storageKey, content);
        }
      })
      .catch(() => { /* no local copy, no reachable server copy — stay empty */ });
  }, [storedReports, storageKey]);

  const generateMut = useMutation({
    mutationFn: async () => {
      return agentsApi.report({
        scan_ids: scanIds ?? [],
        target: workspace?.name ?? 'Workspace',
        scan_name: workspace?.name ?? 'Workspace Report',
        workspace_id: workspaceId,
        stats: {
          workspace_id: workspaceId,
          workspace_name: workspace?.name,
          ...((summary as Record<string, unknown>) ?? {}),
        },
      });
    },
    onSuccess: (data) => {
      const reportData = data?.data ?? data;
      const md = reportData?.report ?? reportData?.content ?? reportData?.markdown ?? JSON.stringify(data, null, 2);
      setReportContent(md);
      safeSetItem(storageKey, md);
      queryClient.invalidateQueries({ queryKey: ['stored-reports-workspace', workspaceId] });
    },
    onError: (err: Error) => {
      console.error('Failed to generate workspace report:', err);
    },
  });

  const deleteMut = useMutation({
    mutationFn: async () => {
      if (serverReportId) {
        await reportsApi.delete(serverReportId);
      }
    },
    onSuccess: () => {
      safeRemoveItem(storageKey);
      setReportContent('');
      setServerReportId(null);
      setShowDeleteConfirm(false);
      queryClient.invalidateQueries({ queryKey: ['stored-reports-workspace', workspaceId] });
    },
    onError: () => {
      safeRemoveItem(storageKey);
      setReportContent('');
      setServerReportId(null);
      setShowDeleteConfirm(false);
    },
  });

  const generateClientReport = useCallback(() => {
    const stats = (summary as Record<string, unknown>)?.summary as Record<string, unknown> ?? summary ?? {};
    const statsObj = (stats?.statistics ?? stats) as Record<string, number>;
    const lines = [
      `# Workspace Report: ${workspace?.name ?? 'Unknown'}`,
      '',
      `**Workspace ID:** \`${workspaceId}\``,
      `**Description:** ${workspace?.description || 'N/A'}`,
      `**Generated:** ${new Date().toLocaleString()}`,
      '',
      '---',
      '',
      '## Overview',
      '',
      `- **Targets:** ${statsObj?.target_count ?? 'N/A'}`,
      `- **Scans:** ${statsObj?.scan_count ?? 'N/A'}`,
      `- **Total Events:** ${statsObj?.total_events ?? 'N/A'}`,
      `- **Correlations:** ${statsObj?.correlation_count ?? 'N/A'}`,
      '',
      '## Analysis',
      '',
      '> *Edit this section to add your cross-scan threat analysis and insights.*',
      '',
      '## Recommendations',
      '',
      '1. Review all high-risk correlation findings across linked scans.',
      '2. Identify patterns across multiple targets in this workspace.',
      '3. Escalate critical findings to the security team.',
      '',
      '---',
      '*Report generated by SpiderFoot Workspace Analyzer*',
    ];
    const md = lines.join('\n');
    setReportContent(md);
    safeSetItem(storageKey, md);
  }, [workspace, workspaceId, summary, storageKey]);

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

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-foreground flex items-center gap-2">
          <Brain className="h-5 w-5 text-spider-400" /> AI Report
        </h2>
        <div className="flex items-center gap-2">
          {reportContent && !isEditing && (
            <>
              <button className="btn-secondary text-xs" onClick={startEditing}>
                <Edit3 className="h-3 w-3" /> Edit
              </button>
              <button
                className="btn-secondary text-xs text-red-400 hover:text-red-300"
                onClick={() => setShowDeleteConfirm(true)}
                title="Delete this report and start again"
              >
                <Trash2 className="h-3 w-3" /> Delete
              </button>
            </>
          )}
          {isEditing && (
            <>
              <button className="btn-secondary text-xs" onClick={() => setIsEditing(false)}>Cancel</button>
              <button className="btn-primary text-xs" onClick={saveEdit}><Save className="h-3 w-3" /> Save</button>
            </>
          )}
          <button className="btn-primary text-xs" onClick={() => generateMut.mutate()} disabled={generateMut.isPending}>
            {generateMut.isPending ? <><Loader2 className="h-3 w-3 animate-spin" /> Generating CTI Report...</> : <><Sparkles className="h-3 w-3" /> AI Report</>}
          </button>
          {!reportContent && (
            <button className="btn-secondary text-xs" onClick={generateClientReport}>
              <FileText className="h-3 w-3" /> Quick
            </button>
          )}
        </div>
      </div>

      {generateMut.isError && (
        <div className="flex items-center gap-2 mb-3 p-2 bg-yellow-900/10 border border-yellow-700/30 rounded-lg text-xs text-yellow-300">
          <AlertTriangle className="h-3.5 w-3.5" />
          <span>AI report generation failed: {(generateMut.error as Error)?.message ?? 'Unknown error'}. <button className="underline" onClick={generateClientReport}>Use quick report</button></span>
        </div>
      )}

      {isEditing ? (
        <textarea
          ref={editorRef}
          value={editContent}
          onChange={(e) => setEditContent(e.target.value)}
          className="w-full bg-dark-900 text-dark-200 font-mono text-xs p-3 focus:outline-none rounded-lg resize-y border border-dark-700"
          style={{ minHeight: '400px' }}
          spellCheck={false}
        />
      ) : reportContent ? (
        <div className="max-h-[80vh] overflow-y-auto pr-2">
          <MarkdownRenderer content={reportContent} className="prose-sm" />
        </div>
      ) : (
        <div className="text-center py-8 text-dark-500">
          <Brain className="h-10 w-10 mx-auto mb-2 opacity-30" />
          <p className="text-sm">No report yet. Generate one to get started.</p>
        </div>
      )}

      <ConfirmDialog
        open={showDeleteConfirm}
        title="Delete this report?"
        message="This permanently deletes the saved workspace report (server-side and locally). The underlying scans are untouched — you can generate a new report immediately after."
        confirmLabel={deleteMut.isPending ? 'Deleting…' : 'Delete'}
        danger
        onConfirm={() => deleteMut.mutate()}
        onCancel={() => setShowDeleteConfirm(false)}
      />
    </div>
  );
}
