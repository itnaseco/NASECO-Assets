from frappe.model.document import Document
from frappe.model.naming import make_autoname

from naseco_assets.naseco_assets.asset_hooks import (
	on_submit_fixed_asset_request,
	on_update_after_submit_fixed_asset_request,
	validate_fixed_asset_request,
)


class FixedAssetRequest(Document):
	def autoname(self):
		self.name = make_autoname("FAR-.YYYY.-.#####")

	def validate(self):
		validate_fixed_asset_request(self)

	def on_submit(self):
		on_submit_fixed_asset_request(self)

	def on_update_after_submit(self):
		on_update_after_submit_fixed_asset_request(self)
