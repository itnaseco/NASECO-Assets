from naseco_assets.naseco_assets.report._shared import execute_report


def execute(filters=None):
	return execute_report("total_cost_of_ownership_report", filters)
