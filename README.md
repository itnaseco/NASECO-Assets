### NASECO Assets

Fixed asset governance layer for ERPNext Assets.

This app extends ERPNext’s standard `Asset` module without modifying core files. It adds custom DocTypes, custom fields, workflows, scheduled alerts, dashboard cards, and report scaffolding for fixed-asset lifecycle control.

### What’s In Place

- Core custom DocTypes for:
  - Fixed Asset Request
  - Fixed Asset CAPEX Plan
  - Asset Insurance Policy
  - Asset Insurance Claim
  - Asset Maintenance Plan
  - Asset Usage Reading
  - CIP Capitalization Request
- Child tables for asset technical specs, insurance policy items, and maintenance checklists.
- Custom fields and validation hooks for ERPNext `Asset`, `Asset Category`, purchasing docs, and `Project`.
- Scheduled notification framework for expiry, overdue, and exception alerts.
- Report framework for the fixed-asset register, CAPEX, insurance, and acquisition pipeline.

### Installation

```bash
cd /path/to/bench
bench --site naseco.local install-app naseco_assets
bench --site naseco.local migrate
bench --site naseco.local clear-cache
```

### Required ERPNext Setup

- Create or confirm these master data records:
  - `Branch`
  - `Department`
  - `Location`
  - `Employee`
  - `Cost Center`
  - `Asset Category`
  - fixed-asset `Item` records for each asset category
- Ensure the company has a default `Company` and the asset accounts are configured in ERPNext.
- Create at least one `Location` called `Unassigned` if the seed patch has not yet been run.

### Migration Notes

- The app ships with patch hooks in `naseco_assets/patches.txt`.
- Run `bench migrate` after pulling changes so the custom fields and reference data are created.
- The first migration should seed:
  - roles
  - workflow action masters
  - workflows
  - number cards
  - workspace
  - the default `Unassigned` location

### Asset Lifecycle

1. Create a `Fixed Asset Request`.
2. Review CAPEX budget availability.
3. Create the `Material Request` and follow procurement through PO, receipt, and invoice.
4. Create the `CIP Capitalization Request` when construction or installation is complete.
5. Set the ERPNext `Available-for-use Date` and submit the `Asset`.
6. Track location and custody through ERPNext `Asset Movement`, and track insurance and maintenance through the custom docs.

### Depreciation Policy

- The asset category custom fields can supply default policy hints.
- The app blocks depreciation for non-depreciable categories.
- ERPNext’s `Available-for-use Date` controls when depreciation can begin.
- Finance Manager approval is required to override useful life, residual value, or depreciation method after capitalization.

### CAPEX Controls

- `Fixed Asset CAPEX Plan` stores approved budget, commitments, actual spend, and remaining balance.
- `Fixed Asset Request` validates against the linked CAPEX balance.
- Purchase documents carry custom links back to the request and CAPEX plan.

### Insurance Tracking

- `Asset Insurance Policy` tracks coverage periods and covered assets.
- Alerts are scheduled for 90, 60, 30, 14, and 7 day windows.
- `Asset Insurance Claim` records incidents and claim status.

### Permissions

- `Asset Administrator`: master data, custody, insurance, and operational reporting.
- `Finance Manager`: CAPEX, capitalization, depreciation control, and approvals.
- `Department Manager`: fixed asset request creation and approval.
- `Internal Auditor`: read-only plus exception reporting.
- `Executive Viewer`: dashboard and report visibility.

### Extending the App

Most of the business logic lives in:

- `naseco_assets/naseco_assets/lifecycle.py`
- `naseco_assets/naseco_assets/notifications.py`
- `naseco_assets/naseco_assets/report/_shared.py`

If you want the next implementation wave, the natural follow-ups are:

1. Add the remaining report wrappers.
2. Add dashboard charts for NBV, CAPEX, and maintenance.
3. Add tests for all approval and capitalization flows.
