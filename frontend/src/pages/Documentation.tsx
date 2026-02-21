import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { dataApi, Module } from '../lib/api';
import { Search, Cpu, Tag, ChevronRight, ChevronDown, BookOpen, Layers, Shield, ExternalLink } from 'lucide-react';

export default function DocumentationPage() {
  const [search, setSearch] = useState('');
  const [selectedModule, setSelectedModule] = useState<Module | null>(null);
  const [activeTab, setActiveTab] = useState<'modules' | 'events' | 'guides'>('modules');

  const { data: modulesData } = useQuery({
    queryKey: ['doc-modules'],
    queryFn: ({ signal }) => dataApi.modules({ page: 1, page_size: 500 }, signal),
  });
  const { data: entityData } = useQuery({
    queryKey: ['doc-entity-types'],
    queryFn: ({ signal }) => dataApi.entityTypes(signal),
  });
  const { data: catData } = useQuery({
    queryKey: ['doc-module-categories'],
    queryFn: ({ signal }) => dataApi.moduleCategories(signal),
  });

  const modules = modulesData?.items ?? [];
  const entityTypes = entityData?.entity_types ?? [];
  const categories = catData?.module_categories ?? [];

  const filtered = modules.filter(
    (m) =>
      m.name.toLowerCase().includes(search.toLowerCase()) ||
      (m.descr ?? m.description ?? '').toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-spider-500" /> Documentation
          </h1>
          <p className="text-dark-400 text-sm mt-1">
            Browse module reference, event types, and usage guides
          </p>
        </div>
        <a
          href="https://www.spiderfoot.net/documentation/"
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2 text-sm bg-dark-800 border border-dark-700 rounded-lg text-dark-300 hover:text-foreground hover:border-dark-500 transition-colors"
        >
          <ExternalLink className="h-4 w-4" /> Online Docs
        </a>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-dark-800 rounded-lg p-1 w-fit">
        {(['modules', 'events', 'guides'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setSelectedModule(null); }}
            className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
              activeTab === tab
                ? 'bg-spider-600 text-white'
                : 'text-dark-400 hover:text-foreground'
            }`}
          >
            {tab === 'modules' ? 'Modules' : tab === 'events' ? 'Event Types' : 'Guides'}
          </button>
        ))}
      </div>

      {activeTab === 'modules' && !selectedModule && (
        <>
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search modules..."
              className="w-full pl-10 pr-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-spider-500/50"
            />
          </div>

          {/* Category badges */}
          <div className="flex flex-wrap gap-2">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setSearch(cat)}
                className="px-3 py-1 text-xs bg-dark-800 border border-dark-700 text-dark-300 rounded-full hover:border-spider-500/50 hover:text-spider-400 transition-colors"
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="grid gap-2">
            {filtered.map((mod) => (
              <button
                key={mod.name}
                onClick={() => setSelectedModule(mod)}
                className="flex items-center gap-4 p-4 bg-dark-800/60 border border-dark-700 rounded-lg hover:border-dark-500 transition-colors text-left group"
              >
                <Cpu className="h-5 w-5 text-spider-500 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-foreground">{mod.name}</p>
                  <p className="text-xs text-dark-400 truncate">{mod.descr ?? mod.description}</p>
                </div>
                {(mod.cats?.length) && (
                  <span className="px-2 py-0.5 text-[10px] bg-dark-700 text-dark-300 rounded-full flex-shrink-0">
                    {mod.cats[0]}
                  </span>
                )}
                <ChevronRight className="h-4 w-4 text-dark-600 group-hover:text-dark-400 flex-shrink-0" />
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="text-dark-500 text-sm py-8 text-center">No modules found.</p>
            )}
          </div>
        </>
      )}

      {activeTab === 'modules' && selectedModule && (
        <div className="space-y-6">
          <button
            onClick={() => setSelectedModule(null)}
            className="text-sm text-spider-400 hover:text-spider-300 flex items-center gap-1"
          >
            ← Back to modules
          </button>

          <div className="bg-dark-800/60 border border-dark-700 rounded-xl p-6 space-y-4">
            <div className="flex items-start gap-4">
              <Cpu className="h-8 w-8 text-spider-500 mt-1" />
              <div>
                <h2 className="text-xl font-bold text-foreground">{selectedModule.name}</h2>
                <p className="text-dark-400 text-sm mt-1">
                  {selectedModule.descr ?? selectedModule.description}
                </p>
                {selectedModule.cats?.length && (
                  <span className="inline-block mt-2 px-3 py-1 text-xs bg-spider-600/20 text-spider-400 rounded-full">
                    {selectedModule.cats.join(', ')}
                  </span>
                )}
              </div>
            </div>

            {selectedModule.provides && selectedModule.provides.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-dark-300 mb-2">Produces</h3>
                <div className="flex flex-wrap gap-1.5">
                  {selectedModule.provides.map((e) => (
                    <span key={e} className="px-2 py-0.5 text-xs bg-green-900/30 text-green-400 rounded-full border border-green-800/40">
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedModule.consumes && selectedModule.consumes.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-dark-300 mb-2">Consumes</h3>
                <div className="flex flex-wrap gap-1.5">
                  {selectedModule.consumes.map((e) => (
                    <span key={e} className="px-2 py-0.5 text-xs bg-blue-900/30 text-blue-400 rounded-full border border-blue-800/40">
                      {e}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedModule.flags && selectedModule.flags.length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-dark-300 mb-2">Flags</h3>
                <div className="flex flex-wrap gap-1.5">
                  {selectedModule.flags.map((f) => (
                    <span key={f} className="px-2 py-0.5 text-xs bg-yellow-900/30 text-yellow-400 rounded-full border border-yellow-800/40">
                      {f}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedModule.opts && Object.keys(selectedModule.opts).length > 0 && (
              <div>
                <h3 className="text-sm font-semibold text-dark-300 mb-2">Configuration Options</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-dark-700">
                        <th className="text-left py-2 px-3 text-dark-400 font-medium">Option</th>
                        <th className="text-left py-2 px-3 text-dark-400 font-medium">Default</th>
                        <th className="text-left py-2 px-3 text-dark-400 font-medium">Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(selectedModule.opts).map(([key, val]) => (
                        <tr key={key} className="border-b border-dark-700/50">
                          <td className="py-2 px-3 font-mono text-spider-400">{key}</td>
                          <td className="py-2 px-3 text-dark-400 font-mono">{val === '' || val === null ? '—' : String(val)}</td>
                          <td className="py-2 px-3 text-dark-300">{selectedModule.optdescs?.[key] || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'events' && (
        <div className="space-y-4">
          <p className="text-sm text-dark-400">
            SpiderFoot uses a type system for data elements discovered during scans. Each event type represents a category of intelligence.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {entityTypes.map((t) => (
              <div
                key={t}
                className="flex items-center gap-3 p-3 bg-dark-800/60 border border-dark-700 rounded-lg"
              >
                <Tag className="h-4 w-4 text-spider-500 flex-shrink-0" />
                <span className="text-sm text-dark-200 font-mono truncate">{t}</span>
              </div>
            ))}
            {entityTypes.length === 0 && (
              <p className="text-dark-500 text-sm col-span-full text-center py-8">
                No event types loaded.
              </p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'guides' && (
        <GuidesPanel />
      )}
    </div>
  );
}

/* ───────────────────────────────────────────────────────────── */
/* Guides Panel — fully navigable                                */
/* ───────────────────────────────────────────────────────────── */

interface GuideSection {
  title: string;
  content: string;
}

interface Guide {
  title: string;
  desc: string;
  icon: React.ComponentType<{ className?: string }>;
  sections: GuideSection[];
}

const GUIDES: Guide[] = [
  {
    title: 'Getting Started',
    desc: 'Learn how to run your first scan, interpret results, and configure modules.',
    icon: BookOpen,
    sections: [
      {
        title: 'Creating a scan target',
        content: `To create a scan, navigate to **New Scan** from the sidebar. Enter a target — this can be a domain name (e.g. example.com), an IP address, email address, username, phone number, or even a human name.\n\nSpiderFoot will auto-detect the target type and enable only the modules relevant to that type. You can override the detection by selecting a specific target type from the dropdown.`,
      },
      {
        title: 'Choosing modules or scan type',
        content: `SpiderFoot offers individual module selection or AI-powered scan configuration.\n\n**Manual selection**: Pick specific modules like sfp_dnsresolve, sfp_portscan_tcp, etc.\n\n**AI-powered**: Use the "AI Recommend" feature to get an optimal module set for your objective (e.g. reconnaissance, vulnerability assessment) while balancing stealth, speed, and coverage.\n\n**Presets**: Quick configuration profiles like "Passive Only", "Full Scan", and "Stealth" are available for common scenarios.`,
      },
      {
        title: 'Viewing scan results and correlations',
        content: `After a scan completes, you can view results organized by:\n\n- **Event Types**: INTERNET_NAME, IP_ADDRESS, DOMAIN_NAME, etc.\n- **Modules**: Which module produced each finding\n- **Timeline**: Chronological discovery order\n- **Graph**: Visual relationship map between entities\n\nClick on any event to see its full details, source chain, and related findings. Use the **Correlations** tab to find cross-referenced intelligence patterns.`,
      },
      {
        title: 'Exporting reports (PDF, CSV, JSON)',
        content: `SpiderFoot supports multiple export formats:\n\n- **CSV**: Download all events in a structured spreadsheet format\n- **JSON**: Full machine-readable export including metadata\n- **GEXF**: Graph format for visualization in tools like Gephi\n\nNavigate to a scan's detail page and use the export buttons in the Events tab. You can filter by event type before exporting.`,
      },
    ],
  },
  {
    title: 'Module Reference',
    desc: 'Detailed information about every SpiderFoot module and its options.',
    icon: Cpu,
    sections: [
      {
        title: 'Passive vs Active modules',
        content: `Modules are classified as passive or active:\n\n**Passive modules** query third-party services and APIs without directly interacting with the target. These are safe and stealthy (e.g. sfp_dnsresolve, sfp_shodan, sfp_haveibeenpwned).\n\n**Active modules** directly probe the target infrastructure. These include port scanning, web crawling, and banner grabbing (e.g. sfp_portscan_tcp, sfp_spider). Use with caution and proper authorization.`,
      },
      {
        title: 'API key configuration',
        content: `Many modules require API keys for third-party services. Configure these in **Settings > API Keys**.\n\nCommon services requiring keys:\n- Shodan, Censys (infrastructure search)\n- VirusTotal (malware/threat intelligence)\n- Have I Been Pwned (breach data)\n- SecurityTrails (DNS history)\n- Hunter.io (email discovery)\n\nModules degrade gracefully if no API key is provided — they simply skip their lookups.`,
      },
      {
        title: 'Module dependencies',
        content: `Modules form an event-driven pipeline. Each module:\n\n- **Consumes** specific event types (e.g. INTERNET_NAME)\n- **Produces** new event types (e.g. IP_ADDRESS)\n\nWhen a module produces an event, other modules that consume that event type automatically process it. This creates a cascading discovery chain.\n\nView the full dependency graph in the **Modules** tab under Documentation.`,
      },
      {
        title: 'Custom module development',
        content: `Create custom modules by implementing the SpiderFoot module interface:\n\n1. Create a new Python file in the modules/ directory\n2. Define \`watchedEvents()\` — events your module consumes\n3. Define \`producedEvents()\` — events your module produces\n4. Implement \`handleEvent()\` — your processing logic\n5. Use \`self.notifyListeners()\` to emit new events\n\nSee existing modules as templates. The module framework handles registration, configuration, and error recovery automatically.`,
      },
    ],
  },
  {
    title: 'Architecture',
    desc: "Understand SpiderFoot's microservices architecture, event system, and data flow.",
    icon: Layers,
    sections: [
      {
        title: 'Microservices overview (FastAPI, Celery, Redis)',
        content: `SpiderFoot v5 uses a microservices architecture:\n\n- **FastAPI**: REST API server handling all HTTPS requests\n- **Celery**: Distributed task queue for scan execution\n- **Redis**: Message broker for Celery + caching layer\n- **PostgreSQL**: Primary persistent data store\n- **Traefik**: Reverse proxy with TLS termination\n- **Flower**: Celery task monitoring dashboard\n- **MinIO**: Object storage for reports and artifacts\n\nAll services are orchestrated via Docker Compose.`,
      },
      {
        title: 'Event-driven data pipeline',
        content: `The scan engine uses an event-driven architecture:\n\n1. Scanner receives a target and module list\n2. ROOT event is created for the target\n3. Each module watches for specific event types\n4. When a module discovers data, it emits new events\n5. Other modules consume those events, creating a cascade\n6. All events are stored in PostgreSQL with full provenance\n\nThis architecture enables parallel processing and modular extensibility.`,
      },
      {
        title: 'Database schema (PostgreSQL)',
        content: `Core PostgreSQL tables:\n\n- **tbl_scan_instance**: Scan metadata (ID, name, target, status, timestamps)\n- **tbl_scan_results**: All discovered events with module attribution\n- **tbl_scan_log**: Scan execution logs\n- **tbl_event_types**: Registry of all event type definitions\n- **tbl_scan_config**: Per-scan configuration snapshots\n\nPostgreSQL enables concurrent access, full-text search, and is used as the primary deployment database.`,
      },
      {
        title: 'Docker Compose deployment',
        content: `Deploy with: \`docker compose -f docker-compose-microservices.yml up -d\`\n\nKey services:\n- **sf-api**: FastAPI backend (port 443 via Traefik)\n- **celery-worker**: Scan execution workers\n- **celery-beat**: Periodic task scheduler\n- **redis**: Message broker and cache\n- **postgres**: Primary database\n- **flower**: Celery monitoring (accessible at /flower/)\n- **traefik**: Reverse proxy and TLS\n\nAll services run on internal Docker networks with only Traefik exposed externally.`,
      },
    ],
  },
  {
    title: 'Security & Access',
    desc: 'Configure SSO, RBAC, API keys, and audit logging for your deployment.',
    icon: Shield,
    sections: [
      {
        title: 'Setting up SAML / OIDC SSO',
        content: `SpiderFoot supports SSO via SAML and OpenID Connect:\n\n1. Configure your identity provider (Okta, Azure AD, Keycloak)\n2. Set SSO environment variables in docker-compose\n3. Map IdP groups to SpiderFoot roles\n\nEnvironment variables:\n- \`SF_SSO_PROVIDER\`: saml or oidc\n- \`SF_SSO_CLIENT_ID\`: OAuth2 client ID\n- \`SF_SSO_ISSUER_URL\`: Identity provider URL\n- \`SF_SSO_REDIRECT_URI\`: Callback URL`,
      },
      {
        title: 'Role-Based Access Control (RBAC)',
        content: `RBAC roles control access to SpiderFoot features:\n\n- **Admin**: Full access — manage users, settings, and all scans\n- **Analyst**: Create and view scans, export results\n- **Viewer**: Read-only access to scan results\n- **API**: Programmatic access with rate limiting\n\nConfigure RBAC in Settings > Access Control. API keys inherit the role of the user who created them.`,
      },
      {
        title: 'API key management',
        content: `API keys provide programmatic access to SpiderFoot:\n\n1. Navigate to **Settings > API Keys**\n2. Click "Generate New Key"\n3. Set permissions and expiration\n4. Store the key securely — it's shown only once\n\nUse the API key in requests via the \`Authorization: Bearer <key>\` header. Keys can be revoked at any time from the Settings page.`,
      },
      {
        title: 'Audit log review and compliance',
        content: `SpiderFoot logs all significant actions for audit compliance:\n\n- Scan creation, modification, and deletion\n- User authentication events\n- Configuration changes\n- API key usage\n- Data exports\n\nAccess audit logs via the API: \`GET /api/config/history\`. Logs include timestamps, user identity, action type, and affected resources. Use Grafana dashboards for visual audit trail analysis.`,
      },
    ],
  },
];

function GuidesPanel() {
  const [expandedGuide, setExpandedGuide] = useState<string | null>(null);
  const [expandedSection, setExpandedSection] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      {/* Guide navigation sidebar + content */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Left nav — guide list */}
        <div className="md:col-span-1 space-y-2">
          {GUIDES.map((guide) => (
            <button
              key={guide.title}
              onClick={() => {
                setExpandedGuide(expandedGuide === guide.title ? null : guide.title);
                setExpandedSection(null);
              }}
              className={`w-full flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${
                expandedGuide === guide.title
                  ? 'bg-spider-600/10 border-spider-600/40 text-foreground'
                  : 'bg-dark-800/60 border-dark-700 text-dark-300 hover:border-dark-500 hover:text-foreground'
              }`}
            >
              <guide.icon className={`h-5 w-5 flex-shrink-0 ${expandedGuide === guide.title ? 'text-spider-400' : 'text-dark-500'}`} />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium">{guide.title}</p>
                <p className="text-xs text-dark-500 truncate">{guide.desc}</p>
              </div>
              <ChevronRight className={`h-4 w-4 flex-shrink-0 transition-transform ${expandedGuide === guide.title ? 'rotate-90 text-spider-400' : 'text-dark-600'}`} />
            </button>
          ))}
        </div>

        {/* Right content — sections */}
        <div className="md:col-span-2">
          {expandedGuide ? (
            <div className="space-y-3">
              {GUIDES.find((g) => g.title === expandedGuide)?.sections.map((section) => (
                <div key={section.title} className="bg-dark-800/60 border border-dark-700 rounded-xl overflow-hidden">
                  <button
                    onClick={() => setExpandedSection(expandedSection === section.title ? null : section.title)}
                    className="w-full flex items-center justify-between p-4 text-left hover:bg-dark-700/30 transition-colors"
                  >
                    <span className="text-sm font-medium text-foreground">{section.title}</span>
                    <ChevronDown className={`h-4 w-4 text-dark-400 transition-transform ${expandedSection === section.title ? 'rotate-180' : ''}`} />
                  </button>
                  {expandedSection === section.title && (
                    <div className="px-4 pb-4 animate-fade-in">
                      <div className="prose prose-sm prose-invert max-w-none">
                        {section.content.split('\n\n').map((para, i) => (
                          <p key={i} className="text-sm text-dark-300 leading-relaxed mb-3 last:mb-0">
                            {para.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((segment, j) => {
                              if (segment.startsWith('**') && segment.endsWith('**')) {
                                return <strong key={j} className="text-foreground font-semibold">{segment.slice(2, -2)}</strong>;
                              }
                              if (segment.startsWith('`') && segment.endsWith('`')) {
                                return <code key={j} className="px-1.5 py-0.5 bg-dark-700 text-spider-400 rounded text-xs font-mono">{segment.slice(1, -1)}</code>;
                              }
                              return <span key={j}>{segment}</span>;
                            })}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-dark-500">
              <div className="text-center">
                <BookOpen className="h-12 w-12 mx-auto mb-3 text-dark-600" />
                <p className="text-sm">Select a guide from the left to read its sections</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
