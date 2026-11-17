# AI Super Salesman — Operating System Plan

## Goal
Build a low-cost, phone-friendly digital-products business. The owner controls money and final approvals. Agents handle repeatable research, product packaging, marketing preparation, customer support, order administration, and reporting.

## Agent roles
1. Product Builder: maintain a product catalogue, build and test one product at a time, prepare release notes, demo, screenshots, license, and support guide.
2. Market Research: identify relevant public business prospects and buying signals; record source URL, date, fit reason, and confidence. Never invent a lead or claim a person has agreed to buy.
3. Marketing: create product pages, social posts, FAQs, demo scripts, and channel-specific campaign drafts.
4. Sales: answer inbound enquiries, qualify needs, recommend a matching product, quote only approved prices, and create an order draft.
5. Customer Success: deliver setup instructions and support after payment confirmation; collect feedback and issue reports.
6. Finance & Analytics: track order amount, payment status, expenses, refunds, and net revenue; produce daily/weekly reports.

## Automation boundaries
- Research can run on a schedule only after a permitted data source/API is configured.
- Outbound messages must use channels and audiences where the owner has permission to contact people. No scraping private data, unsolicited bulk messaging, fake identities, fake reviews, or bypassing platform limits.
- Telegram bots cannot initiate a conversation with arbitrary users; a user generally must start the bot first. Other channels require their own official integrations and permissions.
- The agent may prepare an order and send payment instructions from owner-approved templates. It must not claim payment is received based only on a customer screenshot or an unverified message.
- The owner alone confirms incoming money in their actual payment account. Only then may the delivery workflow release paid files or license keys.
- Refunds, discounts outside approved rules, account changes, spending, and legal commitments require owner approval.
- Do not store payment PINs, passwords, OTPs, or full card details.

## Core data records
- Product: id, name, description, version, demo_url, delivery_asset, approved_price, status, support_notes.
- Prospect: id, business/person label, public_source_url, channel, relevance_reason, contact_permission, status, last_contact_at.
- Conversation: id, prospect_id, channel, messages, consent/status, assigned_agent, next_action.
- Order: id, product_id, buyer_contact, quantity, quoted_price, payment_method, payment_reference, payment_status, owner_verified_at, delivery_status.
- Expense: id, category, amount, currency, date, evidence_note.
- AgentRun: id, agent_name, started_at, completed_at, outcome, error, human_approval_required.

## Required system components
- Owner dashboard: products, leads, conversations, orders, payment verification queue, revenue, expenses, and agent activity.
- Secure backend/API: agent orchestration, database, scheduled jobs, access control, audit log, and webhook endpoints.
- AI provider: API key stored only as a server-side secret, never in browser source or public GitHub files.
- Channel adapters: add one official channel at a time; start with inbound Telegram bot messages, then other approved channels.
- Payment workflow: manual owner verification first; automated payment webhooks only if a supported provider and merchant account are available.
- Delivery service: release the correct product after owner verification; log each delivery.
- Monitoring: run history, failures, daily digest, backup/export, and rate limits.

## Zero-budget-first deployment
Use free tiers only where available and verify current limits before relying on them. GitHub Pages can host static product demos/dashboard UI but cannot safely host API secrets or run a persistent private agent backend. A server-side host/database and an AI API allowance are required for genuine autonomous operation. Free tiers may sleep, throttle, or change; continuous 24/7 operation is not guaranteed at zero cost.

## Rollout gates
1. Publish a tested product catalogue and demo.
2. Build owner dashboard and manual CRM/order workflow.
3. Add secure backend, database, audit log, and secrets.
4. Add one AI provider and test cost/usage limits.
5. Connect inbound Telegram bot and test customer support.
6. Add public-prospect research from a permitted source; require review before first contact.
7. Add opt-in/approved follow-up automation with rate limits and unsubscribe handling.
8. Add owner-verified payment and automated delivery.
9. Run end-to-end tests with test orders before real sales.
10. Only call the business automated after scheduled jobs, recovery, monitoring, backups, and all channel permissions have been verified.

## Current known constraints
- Existing Shop Ledger is an offline-first prototype with local browser storage, not yet sale-ready.
- The current GitHub Pages workflow failed because Pages is not enabled/configured for GitHub Actions in repository settings. Enable it in Settings > Pages > Build and deployment > Source: GitHub Actions, then rerun the workflow.
- Do not promise revenue, customers, or fully unattended operation before real integrations and end-to-end tests exist.
