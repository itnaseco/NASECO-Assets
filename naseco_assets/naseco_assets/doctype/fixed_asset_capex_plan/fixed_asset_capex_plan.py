from frappe.model.document import Document
from frappe.model.naming import make_autoname

from naseco_assets.naseco_assets.asset_hooks import refresh_capex_plan_totals, validate_capex_plan


class FixedAssetCAPEXPlan(Document):
	def autoname(self):
		self.name = make_autoname("CAPEX-.YYYY.-.#####")

	def validate(self):
		validate_capex_plan(self)

	def on_update(self):
		refresh_capex_plan_totals(self)
