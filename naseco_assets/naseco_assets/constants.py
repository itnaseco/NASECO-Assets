from __future__ import annotations

ASSET_BUSINESS_CLASSES = [
	"Agricultural Equipment",
	"Processing Equipment",
	"Laboratory Equipment",
	"Fleet",
	"IT Equipment",
	"Buildings",
	"Furniture & Fixtures",
	"Utilities",
	"Construction in Progress",
	"Intangible Fixed Asset",
]

ASSET_CRITICALITY_OPTIONS = ["Low", "Medium", "High", "Critical"]
ASSET_RISK_LEVEL_OPTIONS = ["Low", "Medium", "High"]
ASSET_OPERATIONAL_STATUS_OPTIONS = [
	"Inactive",
	"Active",
	"Idle",
	"Under Maintenance",
	"Damaged",
	"Lost",
	"Retired",
	"Disposed",
]
ASSET_CONDITION_STATUS_OPTIONS = ["New", "Good", "Fair", "Poor", "Damaged", "Obsolete"]
CAPITALIZATION_STATUS_OPTIONS = ["Pending", "Capitalized", "On Hold", "Rejected"]
FUNDING_SOURCE_OPTIONS = ["Company Funded", "Grant Funded", "Loan Funded", "Donated"]
REQUEST_APPROVAL_STATUS_OPTIONS = [
	"Draft",
	"Pending Department Approval",
	"Pending Finance Review",
	"Pending Management Approval",
	"Approved",
	"Rejected",
	"Deferred",
]
CAPEX_PLAN_STATUS_OPTIONS = [
	"Draft",
	"Pending Review",
	"Returned for Revision",
	"Approved",
	"Frozen",
	"Closed",
]
POLICY_STATUS_OPTIONS = ["Active", "Expiring Soon", "Expired", "Cancelled"]
POLICY_APPROVAL_STATUS_OPTIONS = [
	"Draft",
	"Pending Review",
	"Returned for Revision",
	"Approved",
	"Active",
	"Rejected",
	"Cancelled",
]
INSURANCE_COVERAGE_BASIS_OPTIONS = [
	"Selected Assets",
	"Asset Category",
	"Item Code",
	"Branch",
	"Department",
	"Location",
]
CLAIM_STATUS_OPTIONS = ["Draft", "Submitted", "Under Review", "Approved", "Rejected", "Settled"]
MAINTENANCE_STATUS_OPTIONS = ["Active", "Suspended", "Closed"]
USAGE_READING_TYPES = ["Mileage", "Running Hours", "Machine Hours", "Production Units"]
CIP_STATUS_OPTIONS = ["Draft", "Pending Review", "Approved", "Rejected"]
MAINTENANCE_FREQUENCY_OPTIONS = [
	"Weekly",
	"Monthly",
	"Quarterly",
	"Semi-Annual",
	"Annual",
	"Mileage Based",
	"Running Hours Based",
]

ROLE_ASSET_ADMINISTRATOR = "Asset Administrator"
ROLE_FINANCE_MANAGER = "Finance Manager"
ROLE_FIXED_ASSET_ACCOUNTANT = "Fixed Asset Accountant"
ROLE_PROCUREMENT_MANAGER = "Procurement Manager"
ROLE_DEPARTMENT_MANAGER = "Department Manager"
ROLE_BRANCH_MANAGER = "Branch Manager"
ROLE_FLEET_MANAGER = "Fleet Manager"
ROLE_ICT_MANAGER = "ICT Manager"
ROLE_LABORATORY_MANAGER = "Laboratory Manager"
ROLE_FARM_MANAGER = "Farm Manager"
ROLE_INTERNAL_AUDITOR = "Internal Auditor"
ROLE_EXECUTIVE_VIEWER = "Executive Viewer"

ROLE_GROUP_ACCESS = [
	ROLE_ASSET_ADMINISTRATOR,
	ROLE_FINANCE_MANAGER,
	ROLE_FIXED_ASSET_ACCOUNTANT,
	ROLE_PROCUREMENT_MANAGER,
	ROLE_DEPARTMENT_MANAGER,
	ROLE_BRANCH_MANAGER,
	ROLE_FLEET_MANAGER,
	ROLE_ICT_MANAGER,
	ROLE_LABORATORY_MANAGER,
	ROLE_FARM_MANAGER,
	ROLE_INTERNAL_AUDITOR,
	ROLE_EXECUTIVE_VIEWER,
]

NON_DEPRECIABLE_BUSINESS_CLASSES = {"Construction in Progress"}

DEPRECIATION_DEFAULTS = {
	"Buildings": {"method": "Straight Line", "useful_life_years": 35},
	"Agricultural Equipment": {"method": "Straight Line", "useful_life_years": 8},
	"Processing Equipment": {"method": "Straight Line", "useful_life_years": 12},
	"Laboratory Equipment": {"method": "Straight Line", "useful_life_years": 8},
	"Fleet": {"method": "Reducing Balance", "useful_life_years": 6},
	"IT Equipment": {"method": "Straight Line", "useful_life_years": 4},
	"Furniture & Fixtures": {"method": "Straight Line", "useful_life_years": 10},
	"Utilities": {"method": "Straight Line", "useful_life_years": 10},
	"Intangible Fixed Asset": {"method": "Straight Line", "useful_life_years": 4},
}

DEFAULT_LOCATION_NAME = "Unassigned"
