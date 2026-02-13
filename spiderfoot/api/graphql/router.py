"""
FastAPI router that mounts the Strawberry GraphQL endpoint.

Provides:
  - /api/graphql       — GraphQL endpoint + GraphiQL IDE
  - /api/graphql/ws    — GraphQL subscriptions via WebSocket

Usage in main.py:
    from spiderfoot.api.graphql.router import graphql_router
    app.include_router(graphql_router, prefix="/api")
"""
from __future__ import annotations

import logging

from strawberry.fastapi import GraphQLRouter

from .resolvers import schema

_log = logging.getLogger("spiderfoot.api.graphql")

# Create the Strawberry → FastAPI router with subscription support
graphql_router = GraphQLRouter(
    schema,
    path="/graphql",
    graphql_ide="graphiql",           # GraphiQL playground at /api/graphql
    subscription_protocols=["graphql-transport-ws", "graphql-ws"],
)

_log.info("GraphQL router created — endpoint at /api/graphql (subscriptions enabled)")
