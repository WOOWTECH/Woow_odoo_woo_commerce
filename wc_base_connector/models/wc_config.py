# -*- coding: utf-8 -*-
import logging
from odoo import fields, models

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wc_url = fields.Char(
        string="WooCommerce URL",
        config_parameter='wc_base_connector.wc_url',
        help="e.g. https://www.inzense.com.tw",
    )
    wc_username = fields.Char(
        string="WC API Username",
        config_parameter='wc_base_connector.wc_username',
    )
    wc_password = fields.Char(
        string="WC API Password",
        config_parameter='wc_base_connector.wc_password',
    )

    def action_test_wc_connection(self):
        import requests
        ICP = self.env['ir.config_parameter'].sudo()
        url = ICP.get_param('wc_base_connector.wc_url', '')
        username = ICP.get_param('wc_base_connector.wc_username', '')
        password = ICP.get_param('wc_base_connector.wc_password', '')
        if not all([url, username, password]):
            return self._wc_notify("Please fill in WooCommerce connection settings first", 'danger')
        try:
            resp = requests.get(
                f"{url.rstrip('/')}/wp-json/wc/v3/orders",
                auth=(username, password.replace(' ', '')),
                params={'per_page': 1}, timeout=15,
            )
            if resp.status_code == 200:
                total = resp.headers.get('X-WP-Total', '?')
                return self._wc_notify(f"Connection successful! WooCommerce has {total} orders", 'success')
            else:
                return self._wc_notify(f"Connection failed: HTTP {resp.status_code}", 'danger')
        except Exception as e:
            return self._wc_notify(f"Connection error: {str(e)[:100]}", 'danger')

    def _wc_notify(self, message, notif_type='info'):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'WooCommerce', 'message': message, 'type': notif_type, 'sticky': False},
        }
