import { useQuery } from '@tanstack/react-query';
import { tagApi } from '../lib/api';
import { Tag, FolderTree, Plus, Palette } from 'lucide-react';
import { useState } from 'react';

const TAG_COLORS = [
  { name: 'red', class: 'bg-red-500' },
  { name: 'orange', class: 'bg-orange-500' },
  { name: 'yellow', class: 'bg-yellow-500' },
  { name: 'green', class: 'bg-green-500' },
  { name: 'blue', class: 'bg-blue-500' },
  { name: 'purple', class: 'bg-purple-500' },
  { name: 'pink', class: 'bg-pink-500' },
  { name: 'gray', class: 'bg-gray-500' },
  { name: 'teal', class: 'bg-teal-500' },
  { name: 'indigo', class: 'bg-indigo-500' },
];

export default function TagsGroupsPage() {
  const [tab, setTab] = useState<'tags' | 'groups'>('tags');
  const { data: tags } = useQuery({ queryKey: ['tags'], queryFn: tagApi.listTags });
  const { data: groups } = useQuery({ queryKey: ['groups'], queryFn: tagApi.listGroups });
  const { data: stats } = useQuery({ queryKey: ['tag-stats'], queryFn: tagApi.stats });

  const tagList = tags?.tags ?? [];
  const groupList = groups?.groups ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Tags & Groups</h1>
        <button className="btn-primary flex items-center gap-2">
          <Plus className="h-4 w-4" /> {tab === 'tags' ? 'Create Tag' : 'Create Group'}
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="card flex items-center gap-3">
            <Tag className="h-5 w-5 text-spider-400" />
            <div>
              <p className="text-sm text-dark-400">Total Tags</p>
              <p className="text-xl font-bold text-white">{stats.total_tags ?? tagList.length}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <FolderTree className="h-5 w-5 text-blue-400" />
            <div>
              <p className="text-sm text-dark-400">Asset Groups</p>
              <p className="text-xl font-bold text-white">{stats.total_groups ?? groupList.length}</p>
            </div>
          </div>
          <div className="card flex items-center gap-3">
            <Palette className="h-5 w-5 text-purple-400" />
            <div>
              <p className="text-sm text-dark-400">Tagged Resources</p>
              <p className="text-xl font-bold text-white">{stats.total_assignments ?? 0}</p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-dark-800 rounded-lg p-1 w-fit">
        <button
          onClick={() => setTab('tags')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'tags' ? 'bg-spider-600 text-white' : 'text-dark-300 hover:text-white hover:bg-dark-700'
          }`}
        >
          <Tag className="h-4 w-4" /> Tags
        </button>
        <button
          onClick={() => setTab('groups')}
          className={`flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-md transition-colors ${
            tab === 'groups' ? 'bg-spider-600 text-white' : 'text-dark-300 hover:text-white hover:bg-dark-700'
          }`}
        >
          <FolderTree className="h-4 w-4" /> Groups
        </button>
      </div>

      {tab === 'tags' && (
        <div className="flex flex-wrap gap-3">
          {tagList.map((tag: { id: string; name: string; slug?: string; color: string }) => {
            const colorDot = TAG_COLORS.find(c => c.name === tag.color)?.class ?? 'bg-gray-500';
            return (
              <div key={tag.id} className="card flex items-center gap-3 min-w-[200px]">
                <div className={`w-3 h-3 rounded-full ${colorDot}`} />
                <div>
                  <p className="text-white font-medium text-sm">{tag.name}</p>
                  {tag.slug && <p className="text-xs text-dark-500">{tag.slug}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {tab === 'groups' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {groupList.map((g: { id: string; name: string; description: string; member_count?: number }) => (
            <div key={g.id} className="card">
              <div className="flex items-center gap-3 mb-2">
                <FolderTree className="h-5 w-5 text-blue-400" />
                <h3 className="font-semibold text-white">{g.name}</h3>
              </div>
              <p className="text-sm text-dark-300 mb-2">{g.description}</p>
              <p className="text-xs text-dark-400">{g.member_count ?? 0} members</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
