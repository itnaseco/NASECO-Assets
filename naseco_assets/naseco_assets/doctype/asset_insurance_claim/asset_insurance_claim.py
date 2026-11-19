from frappe.model.document import Document

from naseco_assets.naseco_assets.asset_hooks import validate_insurance_claim


class AssetInsuranceClaim(Document):
	def validate(self):
		validate_insurance_claim(self)
