from frappe.model.document import Document

from naseco_assets.naseco_assets.asset_hooks import validate_maintenance_plan


class AssetMaintenancePlan(Document):
	def validate(self):
		validate_maintenance_plan(self)
