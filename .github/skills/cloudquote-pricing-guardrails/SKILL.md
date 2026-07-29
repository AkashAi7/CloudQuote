---
name: cloudquote-pricing-guardrails
description: 'Validate cloud price meters, quantities, units, assumptions, and evidence. Use during BOQ generation, cloud cost comparison, AWS/Azure/GCP pricing, TCO analysis, or whenever source usage is converted to a target-cloud billing meter.'
user-invocable: false
---

# CloudQuote Pricing Guardrails

Validate every source-usage to target-meter conversion before accepting a cost.

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

## Evidence contract

A validation item must contain:

- Source service and quantity description
- Target service/SKU
- Resolved meter and unit
- Missing assumption or dimensional conflict
- Price source and evidence link when available

Do not substitute a guessed value merely to complete scenario totals.
