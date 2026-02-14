import{c as S,r as p,a as x,j as e,o as g,E as C,p as A,q as N,t as P,v as I,x as h}from"./index-DEeuZvqM.js";import{C as f,L as _}from"./layers-Ddu_o6av.js";/**
 * @license lucide-react v0.460.0 - ISC
 *
 * This source code is licensed under the ISC license.
 * See the LICENSE file in the root directory of this source tree.
 */const E=S("Tag",[["path",{d:"M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z",key:"vktsd0"}],["circle",{cx:"7.5",cy:"7.5",r:".5",fill:"currentColor",key:"kqv944"}]]);function R(){var b;const[n,u]=p.useState(""),[s,o]=p.useState(null),[i,a]=p.useState("modules"),{data:d}=x({queryKey:["doc-modules"],queryFn:()=>h.modules({page:1,page_size:500})}),{data:c}=x({queryKey:["doc-entity-types"],queryFn:()=>h.entityTypes()}),{data:r}=x({queryKey:["doc-module-categories"],queryFn:()=>h.moduleCategories()}),m=(d==null?void 0:d.items)??[],v=(c==null?void 0:c.entity_types)??[],w=(r==null?void 0:r.module_categories)??[],y=m.filter(t=>t.name.toLowerCase().includes(n.toLowerCase())||(t.descr??t.description??"").toLowerCase().includes(n.toLowerCase()));return e.jsxs("div",{className:"space-y-6",children:[e.jsxs("div",{className:"flex items-center justify-between",children:[e.jsxs("div",{children:[e.jsxs("h1",{className:"text-2xl font-bold text-white flex items-center gap-2",children:[e.jsx(g,{className:"h-6 w-6 text-spider-500"})," Documentation"]}),e.jsx("p",{className:"text-dark-400 text-sm mt-1",children:"Browse module reference, event types, and usage guides"})]}),e.jsxs("a",{href:"https://www.spiderfoot.net/documentation/",target:"_blank",rel:"noopener noreferrer",className:"flex items-center gap-2 px-4 py-2 text-sm bg-dark-800 border border-dark-700 rounded-lg text-dark-300 hover:text-white hover:border-dark-500 transition-colors",children:[e.jsx(C,{className:"h-4 w-4"})," Online Docs"]})]}),e.jsx("div",{className:"flex gap-1 bg-dark-800 rounded-lg p-1 w-fit",children:["modules","events","guides"].map(t=>e.jsx("button",{onClick:()=>{a(t),o(null)},className:`px-4 py-2 text-sm font-medium rounded-md transition-colors ${i===t?"bg-spider-600 text-white":"text-dark-400 hover:text-white"}`,children:t==="modules"?"Modules":t==="events"?"Event Types":"Guides"},t))}),i==="modules"&&!s&&e.jsxs(e.Fragment,{children:[e.jsxs("div",{className:"relative max-w-md",children:[e.jsx(A,{className:"absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-dark-500"}),e.jsx("input",{value:n,onChange:t=>u(t.target.value),placeholder:"Search modules...",className:"w-full pl-10 pr-4 py-2.5 bg-dark-800 border border-dark-700 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-spider-500/50"})]}),e.jsx("div",{className:"flex flex-wrap gap-2",children:w.map(t=>e.jsx("button",{onClick:()=>u(t),className:"px-3 py-1 text-xs bg-dark-800 border border-dark-700 text-dark-300 rounded-full hover:border-spider-500/50 hover:text-spider-400 transition-colors",children:t},t))}),e.jsxs("div",{className:"grid gap-2",children:[y.map(t=>{var l;return e.jsxs("button",{onClick:()=>o(t),className:"flex items-center gap-4 p-4 bg-dark-800/60 border border-dark-700 rounded-lg hover:border-dark-500 transition-colors text-left group",children:[e.jsx(f,{className:"h-5 w-5 text-spider-500 flex-shrink-0"}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("p",{className:"text-sm font-medium text-white",children:t.name}),e.jsx("p",{className:"text-xs text-dark-400 truncate",children:t.descr??t.description})]}),((l=t.cats)==null?void 0:l.length)&&e.jsx("span",{className:"px-2 py-0.5 text-[10px] bg-dark-700 text-dark-300 rounded-full flex-shrink-0",children:t.cats[0]}),e.jsx(N,{className:"h-4 w-4 text-dark-600 group-hover:text-dark-400 flex-shrink-0"})]},t.name)}),y.length===0&&e.jsx("p",{className:"text-dark-500 text-sm py-8 text-center",children:"No modules found."})]})]}),i==="modules"&&s&&e.jsxs("div",{className:"space-y-6",children:[e.jsx("button",{onClick:()=>o(null),className:"text-sm text-spider-400 hover:text-spider-300 flex items-center gap-1",children:"← Back to modules"}),e.jsxs("div",{className:"bg-dark-800/60 border border-dark-700 rounded-xl p-6 space-y-4",children:[e.jsxs("div",{className:"flex items-start gap-4",children:[e.jsx(f,{className:"h-8 w-8 text-spider-500 mt-1"}),e.jsxs("div",{children:[e.jsx("h2",{className:"text-xl font-bold text-white",children:s.name}),e.jsx("p",{className:"text-dark-400 text-sm mt-1",children:s.descr??s.description}),((b=s.cats)==null?void 0:b.length)&&e.jsx("span",{className:"inline-block mt-2 px-3 py-1 text-xs bg-spider-600/20 text-spider-400 rounded-full",children:s.cats.join(", ")})]})]}),s.provides&&s.provides.length>0&&e.jsxs("div",{children:[e.jsx("h3",{className:"text-sm font-semibold text-dark-300 mb-2",children:"Produces"}),e.jsx("div",{className:"flex flex-wrap gap-1.5",children:s.provides.map(t=>e.jsx("span",{className:"px-2 py-0.5 text-xs bg-green-900/30 text-green-400 rounded-full border border-green-800/40",children:t},t))})]}),s.consumes&&s.consumes.length>0&&e.jsxs("div",{children:[e.jsx("h3",{className:"text-sm font-semibold text-dark-300 mb-2",children:"Consumes"}),e.jsx("div",{className:"flex flex-wrap gap-1.5",children:s.consumes.map(t=>e.jsx("span",{className:"px-2 py-0.5 text-xs bg-blue-900/30 text-blue-400 rounded-full border border-blue-800/40",children:t},t))})]}),s.flags&&s.flags.length>0&&e.jsxs("div",{children:[e.jsx("h3",{className:"text-sm font-semibold text-dark-300 mb-2",children:"Flags"}),e.jsx("div",{className:"flex flex-wrap gap-1.5",children:s.flags.map(t=>e.jsx("span",{className:"px-2 py-0.5 text-xs bg-yellow-900/30 text-yellow-400 rounded-full border border-yellow-800/40",children:t},t))})]}),s.opts&&Object.keys(s.opts).length>0&&e.jsxs("div",{children:[e.jsx("h3",{className:"text-sm font-semibold text-dark-300 mb-2",children:"Configuration Options"}),e.jsx("div",{className:"overflow-x-auto",children:e.jsxs("table",{className:"w-full text-sm",children:[e.jsx("thead",{children:e.jsxs("tr",{className:"border-b border-dark-700",children:[e.jsx("th",{className:"text-left py-2 px-3 text-dark-400 font-medium",children:"Option"}),e.jsx("th",{className:"text-left py-2 px-3 text-dark-400 font-medium",children:"Default"}),e.jsx("th",{className:"text-left py-2 px-3 text-dark-400 font-medium",children:"Description"})]})}),e.jsx("tbody",{children:Object.entries(s.opts).map(([t,l])=>{var k;return e.jsxs("tr",{className:"border-b border-dark-700/50",children:[e.jsx("td",{className:"py-2 px-3 font-mono text-spider-400",children:t}),e.jsx("td",{className:"py-2 px-3 text-dark-400 font-mono",children:l===""||l===null?"—":String(l)}),e.jsx("td",{className:"py-2 px-3 text-dark-300",children:((k=s.optdescs)==null?void 0:k[t])||"—"})]},t)})})]})})]})]})]}),i==="events"&&e.jsxs("div",{className:"space-y-4",children:[e.jsx("p",{className:"text-sm text-dark-400",children:"SpiderFoot uses a type system for data elements discovered during scans. Each event type represents a category of intelligence."}),e.jsxs("div",{className:"grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2",children:[v.map(t=>e.jsxs("div",{className:"flex items-center gap-3 p-3 bg-dark-800/60 border border-dark-700 rounded-lg",children:[e.jsx(E,{className:"h-4 w-4 text-spider-500 flex-shrink-0"}),e.jsx("span",{className:"text-sm text-dark-200 font-mono truncate",children:t})]},t)),v.length===0&&e.jsx("p",{className:"text-dark-500 text-sm col-span-full text-center py-8",children:"No event types loaded."})]})]}),i==="guides"&&e.jsx(T,{})]})}const j=[{title:"Getting Started",desc:"Learn how to run your first scan, interpret results, and configure modules.",icon:g,sections:[{title:"Creating a scan target",content:`To create a scan, navigate to **New Scan** from the sidebar. Enter a target — this can be a domain name (e.g. example.com), an IP address, email address, username, phone number, or even a human name.

SpiderFoot will auto-detect the target type and enable only the modules relevant to that type. You can override the detection by selecting a specific target type from the dropdown.`},{title:"Choosing modules or scan type",content:`SpiderFoot offers individual module selection or AI-powered scan configuration.

**Manual selection**: Pick specific modules like sfp_dnsresolve, sfp_portscan_tcp, etc.

**AI-powered**: Use the "AI Recommend" feature to get an optimal module set for your objective (e.g. reconnaissance, vulnerability assessment) while balancing stealth, speed, and coverage.

**Presets**: Quick configuration profiles like "Passive Only", "Full Scan", and "Stealth" are available for common scenarios.`},{title:"Viewing scan results and correlations",content:`After a scan completes, you can view results organized by:

- **Event Types**: INTERNET_NAME, IP_ADDRESS, DOMAIN_NAME, etc.
- **Modules**: Which module produced each finding
- **Timeline**: Chronological discovery order
- **Graph**: Visual relationship map between entities

Click on any event to see its full details, source chain, and related findings. Use the **Correlations** tab to find cross-referenced intelligence patterns.`},{title:"Exporting reports (PDF, CSV, JSON)",content:`SpiderFoot supports multiple export formats:

- **CSV**: Download all events in a structured spreadsheet format
- **JSON**: Full machine-readable export including metadata
- **GEXF**: Graph format for visualization in tools like Gephi

Navigate to a scan's detail page and use the export buttons in the Events tab. You can filter by event type before exporting.`}]},{title:"Module Reference",desc:"Detailed information about every SpiderFoot module and its options.",icon:f,sections:[{title:"Passive vs Active modules",content:`Modules are classified as passive or active:

**Passive modules** query third-party services and APIs without directly interacting with the target. These are safe and stealthy (e.g. sfp_dnsresolve, sfp_shodan, sfp_haveibeenpwned).

**Active modules** directly probe the target infrastructure. These include port scanning, web crawling, and banner grabbing (e.g. sfp_portscan_tcp, sfp_spider). Use with caution and proper authorization.`},{title:"API key configuration",content:`Many modules require API keys for third-party services. Configure these in **Settings > API Keys**.

Common services requiring keys:
- Shodan, Censys (infrastructure search)
- VirusTotal (malware/threat intelligence)
- Have I Been Pwned (breach data)
- SecurityTrails (DNS history)
- Hunter.io (email discovery)

Modules degrade gracefully if no API key is provided — they simply skip their lookups.`},{title:"Module dependencies",content:`Modules form an event-driven pipeline. Each module:

- **Consumes** specific event types (e.g. INTERNET_NAME)
- **Produces** new event types (e.g. IP_ADDRESS)

When a module produces an event, other modules that consume that event type automatically process it. This creates a cascading discovery chain.

View the full dependency graph in the **Modules** tab under Documentation.`},{title:"Custom module development",content:"Create custom modules by implementing the SpiderFoot module interface:\n\n1. Create a new Python file in the modules/ directory\n2. Define `watchedEvents()` — events your module consumes\n3. Define `producedEvents()` — events your module produces\n4. Implement `handleEvent()` — your processing logic\n5. Use `self.notifyListeners()` to emit new events\n\nSee existing modules as templates. The module framework handles registration, configuration, and error recovery automatically."}]},{title:"Architecture",desc:"Understand SpiderFoot's microservices architecture, event system, and data flow.",icon:_,sections:[{title:"Microservices overview (FastAPI, Celery, Redis)",content:`SpiderFoot v5 uses a microservices architecture:

- **FastAPI**: REST API server handling all HTTPS requests
- **Celery**: Distributed task queue for scan execution
- **Redis**: Message broker for Celery + caching layer
- **PostgreSQL**: Primary persistent data store
- **Traefik**: Reverse proxy with TLS termination
- **Flower**: Celery task monitoring dashboard
- **MinIO**: Object storage for reports and artifacts

All services are orchestrated via Docker Compose.`},{title:"Event-driven data pipeline",content:`The scan engine uses an event-driven architecture:

1. Scanner receives a target and module list
2. ROOT event is created for the target
3. Each module watches for specific event types
4. When a module discovers data, it emits new events
5. Other modules consume those events, creating a cascade
6. All events are stored in PostgreSQL with full provenance

This architecture enables parallel processing and modular extensibility.`},{title:"Database schema (PostgreSQL)",content:`Core PostgreSQL tables:

- **tbl_scan_instance**: Scan metadata (ID, name, target, status, timestamps)
- **tbl_scan_results**: All discovered events with module attribution
- **tbl_scan_log**: Scan execution logs
- **tbl_event_types**: Registry of all event type definitions
- **tbl_scan_config**: Per-scan configuration snapshots

PostgreSQL enables concurrent access, full-text search, and is used as the primary deployment database.`},{title:"Docker Compose deployment",content:`Deploy with: \`docker compose -f docker-compose-microservices.yml up -d\`

Key services:
- **sf-api**: FastAPI backend (port 443 via Traefik)
- **celery-worker**: Scan execution workers
- **celery-beat**: Periodic task scheduler
- **redis**: Message broker and cache
- **postgres**: Primary database
- **flower**: Celery monitoring (accessible at /flower/)
- **traefik**: Reverse proxy and TLS

All services run on internal Docker networks with only Traefik exposed externally.`}]},{title:"Security & Access",desc:"Configure SSO, RBAC, API keys, and audit logging for your deployment.",icon:P,sections:[{title:"Setting up SAML / OIDC SSO",content:`SpiderFoot supports SSO via SAML and OpenID Connect:

1. Configure your identity provider (Okta, Azure AD, Keycloak)
2. Set SSO environment variables in docker-compose
3. Map IdP groups to SpiderFoot roles

Environment variables:
- \`SF_SSO_PROVIDER\`: saml or oidc
- \`SF_SSO_CLIENT_ID\`: OAuth2 client ID
- \`SF_SSO_ISSUER_URL\`: Identity provider URL
- \`SF_SSO_REDIRECT_URI\`: Callback URL`},{title:"Role-Based Access Control (RBAC)",content:`RBAC roles control access to SpiderFoot features:

- **Admin**: Full access — manage users, settings, and all scans
- **Analyst**: Create and view scans, export results
- **Viewer**: Read-only access to scan results
- **API**: Programmatic access with rate limiting

Configure RBAC in Settings > Access Control. API keys inherit the role of the user who created them.`},{title:"API key management",content:`API keys provide programmatic access to SpiderFoot:

1. Navigate to **Settings > API Keys**
2. Click "Generate New Key"
3. Set permissions and expiration
4. Store the key securely — it's shown only once

Use the API key in requests via the \`Authorization: Bearer <key>\` header. Keys can be revoked at any time from the Settings page.`},{title:"Audit log review and compliance",content:`SpiderFoot logs all significant actions for audit compliance:

- Scan creation, modification, and deletion
- User authentication events
- Configuration changes
- API key usage
- Data exports

Access audit logs via the API: \`GET /api/config/history\`. Logs include timestamps, user identity, action type, and affected resources. Use Grafana dashboards for visual audit trail analysis.`}]}];function T(){var i;const[n,u]=p.useState(null),[s,o]=p.useState(null);return e.jsx("div",{className:"space-y-4",children:e.jsxs("div",{className:"grid gap-4 md:grid-cols-3",children:[e.jsx("div",{className:"md:col-span-1 space-y-2",children:j.map(a=>e.jsxs("button",{onClick:()=>{u(n===a.title?null:a.title),o(null)},className:`w-full flex items-center gap-3 p-4 rounded-xl border transition-all text-left ${n===a.title?"bg-spider-600/10 border-spider-600/40 text-white":"bg-dark-800/60 border-dark-700 text-dark-300 hover:border-dark-500 hover:text-white"}`,children:[e.jsx(a.icon,{className:`h-5 w-5 flex-shrink-0 ${n===a.title?"text-spider-400":"text-dark-500"}`}),e.jsxs("div",{className:"flex-1 min-w-0",children:[e.jsx("p",{className:"text-sm font-medium",children:a.title}),e.jsx("p",{className:"text-xs text-dark-500 truncate",children:a.desc})]}),e.jsx(N,{className:`h-4 w-4 flex-shrink-0 transition-transform ${n===a.title?"rotate-90 text-spider-400":"text-dark-600"}`})]},a.title))}),e.jsx("div",{className:"md:col-span-2",children:n?e.jsx("div",{className:"space-y-3",children:(i=j.find(a=>a.title===n))==null?void 0:i.sections.map(a=>e.jsxs("div",{className:"bg-dark-800/60 border border-dark-700 rounded-xl overflow-hidden",children:[e.jsxs("button",{onClick:()=>o(s===a.title?null:a.title),className:"w-full flex items-center justify-between p-4 text-left hover:bg-dark-700/30 transition-colors",children:[e.jsx("span",{className:"text-sm font-medium text-white",children:a.title}),e.jsx(I,{className:`h-4 w-4 text-dark-400 transition-transform ${s===a.title?"rotate-180":""}`})]}),s===a.title&&e.jsx("div",{className:"px-4 pb-4 animate-fade-in",children:e.jsx("div",{className:"prose prose-sm prose-invert max-w-none",children:a.content.split(`

`).map((d,c)=>e.jsx("p",{className:"text-sm text-dark-300 leading-relaxed mb-3 last:mb-0",children:d.split(/(\*\*[^*]+\*\*|\`[^`]+\`)/).map((r,m)=>r.startsWith("**")&&r.endsWith("**")?e.jsx("strong",{className:"text-white font-semibold",children:r.slice(2,-2)},m):r.startsWith("`")&&r.endsWith("`")?e.jsx("code",{className:"px-1.5 py-0.5 bg-dark-700 text-spider-400 rounded text-xs font-mono",children:r.slice(1,-1)},m):e.jsx("span",{children:r},m))},c))})})]},a.title))}):e.jsx("div",{className:"flex items-center justify-center h-64 text-dark-500",children:e.jsxs("div",{className:"text-center",children:[e.jsx(g,{className:"h-12 w-12 mx-auto mb-3 text-dark-600"}),e.jsx("p",{className:"text-sm",children:"Select a guide from the left to read its sections"})]})})})]})})}export{R as default};
//# sourceMappingURL=Documentation-B-uyV6RM.js.map
