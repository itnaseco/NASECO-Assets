from frappe.model.document import Document

from naseco_assets.naseco_assets.asset_hooks import (
	on_submit_cip_capitalization_request,
	validate_cip_capitalization_request,
)


class CIPCapitalizationRequest(Document):
	def validate(self):
		validate_cip_capitalization_request(self)

	def on_submit(self):
		on_submit_cip_capitalization_request(self)
