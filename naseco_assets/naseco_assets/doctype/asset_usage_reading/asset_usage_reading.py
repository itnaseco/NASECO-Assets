from frappe.model.document import Document

from naseco_assets.naseco_assets.asset_hooks import validate_usage_reading


class AssetUsageReading(Document):
	def validate(self):
		validate_usage_reading(self)
