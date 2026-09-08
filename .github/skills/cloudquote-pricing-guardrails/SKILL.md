---
name: cloudquote-pricing-guardrails
description: 'Validate cloud price meters, quantities, units, assumptions, and evidence. Use during BOQ generation, cloud cost comparison, AWS/Azure/GCP pricing, TCO analysis, or whenever source usage is converted to a target-cloud billing meter.'
user-invocable: false
---

# CloudQuote Pricing Guardrails

Validate every source-usage to target-meter conversion before accepting a cost.
These controls apply to every priced mode and every cloud, including a single-cloud
fast path. They are additional to mandatory qualification and human release approvals.

## Validation sequence

1. Classify the source quantity dimension: instance, hour, month, storage capacity, operation, throughput, request, data transfer, license, or composite service.
2. Classify the target meter dimension from its exact `unitOfMeasure`, SKU, product, and meter name.
3. Confirm a defensible conversion exists and list every required assumption.
4. Calculate only when dimensions are compatible and all required assumptions are supplied.
5. Otherwise preserve the resolved meter evidence and emit `[VALIDATE]`; never emit a numeric monthly or annual cost.

## Mandatory flags

Flag these conditions:

- Monthly operations treated as provisioned throughput or throughput-hours
- Monthly hours multiplied by 730 again
- Storage capacity confused with storage transactions, IOPS, throughput, replication, or retrieval
- Network resources priced without processed-data, rule, gateway-hour, or egress dimensions
- Composite managed services represented by only one component meter
- Reservation prices used without term/amortization semantics
- Price unit multipliers such as per 10, 100, 1,000, or 1,000,000 ignored
- Missing request complexity, read/write mix, consistency, redundancy, HA, or workload distribution when required
- Cache or web evidence whose SKU, region, currency, or meter dimension does not match the requested line
- Configuration size multiplied twice by consolidated quantity, HA or environment count
- Blank source price treated as zero actual spend or as a basis for savings
- Term bundled with unapproved AHB, Spot, Dev/Test, utilization or payment assumptions
- Superseded tender rows or stale assumption approvals reused after a scope change

## Evidence contract

A validation item must contain:

- Source service and quantity description
- Target service/SKU
- Resolved meter and unit
- Missing assumption or dimensional conflict
- Price source and evidence link when available

Do not substitute a guessed value merely to complete scenario totals.

## Source and commercial evidence

Use current official APIs/catalogs first; use the official calculator or product
pricing page for uncovered meters. A search provider discovers the page, not the
price. Read the underlying official source; do not price from snippets or memory.
Record URL, accessed UTC, service/SKU, exact region, currency, meter/unit, pricing
model, term/payment, configuration and raw displayed values. Preserve calculator
estimate/export links or screenshots when available. Label derived unit rates and
formulas; do not pretend a calculator total was a published per-unit rate.

Keep list, public commitment, eligible license benefit, negotiated/private, credit,
migration and TCO scenarios distinct. Record utilization, payment, scope, flexibility
and eligibility; equal term lengths do not make commercial programs equivalent.
Do not assume discounts, tax, FX rates, free allowances or quota/capacity availability.
Set price validity and refresh before submission; access date is not an availability SLA.

## Cost completeness and reconciliation

For each category record `Priced`, `Included`, `Not applicable`, `Excluded`, or
`Unknown` with a rationale, source or owner as appropriate:

- Production/non-production compute, platform and licenses.
- Capacity, operations, IOPS/throughput, replicas, snapshots, archives and backups.
- HA/DR, failover/restore tests and standby capacity.
- NAT, gateways, load balancing, IP, DNS, firewall/WAF and DDoS.
- Internet, zone, region, cross-service, hybrid and migration transfer.
- Logs, metrics, traces, retention, SIEM, keys and security management.
- Support, marketplace, managed operations, migration, training and decommissioning.
- Taxes, FX, upfront/one-time charges and credits.

An excluded category is not zero-cost proof. Do not turn an unknown or materially
incomplete cost into an apparently complete total.

Recompute rows/totals from unrounded inputs and expose formulas. State billing-month
convention and unit multipliers. Reconcile recurring monthly, annual and contract-term
amounts separately from upfront/one-time costs. Investigate blank, zero, negative and
TBD values; a field header alone is not evidence.

For comparisons normalize workload, performance, environments, regions, HA/DR, SLA,
RTO/RPO, retention, security, operations, support, licenses and payment terms first.
Show material exceptions beside totals; suppress definitive savings/rankings across
unresolved gaps. Run supported sensitivities for variables that could change the
decision; never represent compiler scenario bundles as every possible TCO model.

## Review status

Keep mandatory eligibility separate from fit scoring and pricing completeness.
Unapproved material assumptions block their affected numeric costs; independent
rows and non-price analysis can continue. A failed mandatory requirement remains
Fail even if that design is cheapest.

Use the typed opportunity review's current baseline and versioned approvals.
On an amendment or scope change, invalidate affected evidence, quantities, conclusions
and approvals. Never self-approve to make the compiler pass. Record reviewer decisions
and source evidence; metadata does not authenticate the identity of a human approver.
