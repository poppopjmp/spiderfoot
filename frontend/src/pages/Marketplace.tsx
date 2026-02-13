import { useQuery } from '@tanstack/react-query';
import { marketplaceApi } from '../lib/api';
import { Store, Download, Star, Package, Search, Filter } from 'lucide-react';
import { useState } from 'react';

export default function MarketplacePage() {
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('all');

  const { data: plugins } = useQuery({ queryKey: ['marketplace-list'], queryFn: marketplaceApi.listPlugins });
  const { data: installed } = useQuery({ queryKey: ['marketplace-installed'], queryFn: marketplaceApi.installed });
  const { data: cats } = useQuery({ queryKey: ['marketplace-categories'], queryFn: marketplaceApi.categories });

  const pluginList = plugins?.plugins ?? [];
  const installedIds = new Set((installed?.plugins ?? []).map((p: { id: string }) => p.id));
  const categories = cats?.categories ?? [];

  const filteredPlugins = pluginList.filter((p: { name: string; category: string }) =>
    (category === 'all' || p.category === category) &&
    (!search || p.name.toLowerCase().includes(search.toLowerCase()))
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-white">Plugin Marketplace</h1>
        <span className="badge badge-info">{pluginList.length} plugins available</span>
      </div>

      {/* Search & filter */}
      <div className="flex gap-4 mb-6">
        <div className="relative flex-1">
          <Search className="h-4 w-4 text-dark-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input className="input-field w-full pl-10" placeholder="Search plugins..." value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <div className="relative">
          <Filter className="h-4 w-4 text-dark-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <select className="input-field pl-10 pr-8" value={category} onChange={(e) => setCategory(e.target.value)}>
            {categories.map((c: string) => (
              <option key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Plugin grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPlugins.map((p: { id: string; name: string; description: string; category: string; version: string; rating: number; downloads: number; author: string }) => (
          <div key={p.id} className="card hover:border-spider-600 border border-transparent transition-colors">
            <div className="flex items-start justify-between mb-3">
              <div className="p-2 rounded-lg bg-spider-600/20">
                <Package className="h-5 w-5 text-spider-400" />
              </div>
              <span className="badge badge-info text-xs">{p.category}</span>
            </div>
            <h3 className="text-white font-semibold">{p.name}</h3>
            <p className="text-sm text-dark-400 mt-1 mb-3">{p.description}</p>
            <div className="flex items-center gap-3 text-xs text-dark-400 mb-4">
              <span>v{p.version}</span>
              <span className="flex items-center gap-1"><Star className="h-3 w-3 text-yellow-400" /> {p.rating}</span>
              <span className="flex items-center gap-1"><Download className="h-3 w-3" /> {p.downloads}</span>
              <span>by {p.author}</span>
            </div>
            <button
              className={`w-full py-2 text-sm font-medium rounded-lg transition-colors ${
                installedIds.has(p.id)
                  ? 'bg-green-600/20 text-green-400 cursor-default'
                  : 'bg-spider-600 text-white hover:bg-spider-500'
              }`}
              disabled={installedIds.has(p.id)}
            >
              {installedIds.has(p.id) ? 'Installed' : 'Install'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
