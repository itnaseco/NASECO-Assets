"""Repair native DocType fields on sites installed before they were packaged."""

from naseco_assets.naseco_assets.setup import ensure_native_custom_fields


def execute() -> None:
	ensure_native_custom_fields()
