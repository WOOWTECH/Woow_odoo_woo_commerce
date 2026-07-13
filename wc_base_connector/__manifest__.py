# -*- coding: utf-8 -*-
{
    "name": "WooCommerce Base Connector",
    "author": "WoowTech",
    "version": "18.0.1.0.0",
    "summary": "WooCommerce connection settings and access groups",
    "license": "LGPL-3",
    "depends": ["base"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/wc_security.xml",
        "views/wc_config_views.xml",
    ],
    "installable": True,
    "auto_install": False,
    "application": False,
    "category": "Sales",
    "post_init_hook": "_migrate_config_keys",
}
