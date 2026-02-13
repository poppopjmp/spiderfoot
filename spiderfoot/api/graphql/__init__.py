"""
GraphQL API for SpiderFoot scan data visualization & management.

Uses Strawberry GraphQL with native FastAPI integration for a type-safe,
code-first GraphQL schema that sits alongside the existing REST API.

Capabilities:
  - **Queries**: scans, events, correlations, statistics, graph
    visualization, cross-scan search, semantic vector search (Qdrant)
  - **Mutations**: start/stop/delete/rerun scans, set false positives
  - **Subscriptions**: real-time scan progress, live event stream

Mount point:   /api/graphql
Playground:    /api/graphql (browser) — GraphiQL IDE
WebSocket:     /api/graphql  (graphql-transport-ws / graphql-ws)
"""
