from naseco_assets.naseco_assets.report._shared import execute_report


def execute(filters=None):
	return execute_report("assets_missing_mandatory_documents_report", filters)
