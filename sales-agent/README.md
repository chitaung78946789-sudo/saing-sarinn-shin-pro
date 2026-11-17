# AI Super Salesman — Owner Dashboard MVP

A phone-friendly static owner dashboard for the digital-products business.

## Included
- Six-agent role board and integration status
- Product catalogue, prospect register, and order register
- Owner-only manual payment confirmation gate
- Activity log and browser localStorage persistence

## Current limitations
This is an MVP interface, not a live autonomous agent system. It does not contact prospects, run AI models, send messages, verify payments with a provider, or deliver files automatically. Those require a secure server-side backend, database, AI provider credentials stored as server secrets, approved channel APIs, and payment/delivery integrations.

Data currently stays in this browser on this device. Export/backup and authentication are not yet implemented. Do not store secrets or sensitive payment data here.

See ../AI_SUPER_SALESMAN_PLAN.md for architecture, safety boundaries, and rollout stages.
