import { useMutation, useQueryClient } from '@tanstack/react-query';
import { workspaceApi } from '../lib/api';
import type { ToastType } from '../components/ui';

type ShowToast = (toast: { type: ToastType; message: string }) => void;

/**
 * Encapsulates all workspace-related mutations to reduce boilerplate in the
 * Workspaces page component.
 */
export function useWorkspaceMutations(
  selectedWorkspace: string | null,
  showToast: ShowToast,
  callbacks?: {
    onCreateSuccess?: () => void;
    onDeleteSuccess?: () => void;
    onUpdateSuccess?: () => void;
    onMultiScanSuccess?: () => void;
  },
) {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description?: string }) => workspaceApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      callbacks?.onCreateSuccess?.();
      showToast({ type: 'success', message: 'Workspace created' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to create workspace' }),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      callbacks?.onDeleteSuccess?.();
      showToast({ type: 'success', message: 'Workspace deleted' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to delete workspace' }),
  });

  const cloneMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.clone(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      showToast({ type: 'success', message: 'Workspace cloned' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to clone workspace' }),
  });

  const setActiveMutation = useMutation({
    mutationFn: (id: string) => workspaceApi.setActive(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      showToast({ type: 'success', message: 'Workspace set as active' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to set active workspace' }),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: { name?: string; description?: string } }) =>
      workspaceApi.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      callbacks?.onUpdateSuccess?.();
      showToast({ type: 'success', message: 'Workspace updated' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to update workspace' }),
  });

  const addTargetMutation = useMutation({
    mutationFn: (data: { target: string; target_type: string }) =>
      workspaceApi.addTarget(selectedWorkspace!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-targets', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      showToast({ type: 'success', message: 'Target added' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to add target. Check the target value and type.' }),
  });

  const deleteTargetMutation = useMutation({
    mutationFn: (targetId: string) =>
      workspaceApi.deleteTarget(selectedWorkspace!, targetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-targets', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      showToast({ type: 'success', message: 'Target removed' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to remove target' }),
  });

  const multiScanMutation = useMutation({
    mutationFn: (modules: string[]) =>
      workspaceApi.multiScan(selectedWorkspace!, modules),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['scans'] });
      queryClient.invalidateQueries({ queryKey: ['workspace-scans', selectedWorkspace] });
      callbacks?.onMultiScanSuccess?.();
      showToast({ type: 'success', message: 'Workspace scan launched! Scans will appear below once started.' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to launch workspace scan' }),
  });

  const linkScanMutation = useMutation({
    mutationFn: (scanId: string) =>
      workspaceApi.linkScan(selectedWorkspace!, scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      showToast({ type: 'success', message: 'Scan linked to workspace' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to link scan' }),
  });

  const unlinkScanMutation = useMutation({
    mutationFn: (scanId: string) =>
      workspaceApi.unlinkScan(selectedWorkspace!, scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspace', selectedWorkspace] });
      queryClient.invalidateQueries({ queryKey: ['workspace-summary', selectedWorkspace] });
      showToast({ type: 'success', message: 'Scan unlinked from workspace' });
    },
    onError: () => showToast({ type: 'error', message: 'Failed to unlink scan' }),
  });

  return {
    createMutation,
    deleteMutation,
    cloneMutation,
    setActiveMutation,
    updateMutation,
    addTargetMutation,
    deleteTargetMutation,
    multiScanMutation,
    linkScanMutation,
    unlinkScanMutation,
  };
}
