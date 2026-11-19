from naseco_assets.naseco_assets.report._shared import execute_report


def execute(filters=None):
	return execute_report("asset_maintenance_due_report", filters)
