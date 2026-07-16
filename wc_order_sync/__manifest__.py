# -*- coding: utf-8 -*-
{
    "name": "WooCommerce Order Sync",
    "author": "WoowTech",
    "version": "18.0.2.1.0",
    "summary": "Sync WooCommerce orders, customers, and products to Odoo",
    "license": "LGPL-3",
    "depends": ["sale_management", "stock", "mail", "wc_base_connector"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.model.access.csv",
        "data/wc_cron.xml",
        "views/wc_config_views.xml",
        "views/wc_sync_queue_views.xml",
        "views/wc_product_map_views.xml",
        "views/wc_partner_map_views.xml",
        "wizard/wc_import_wizard_views.xml",
        "views/wc_menu.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "category": "Sales",
}
