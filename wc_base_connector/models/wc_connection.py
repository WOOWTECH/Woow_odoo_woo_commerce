# -*- coding: utf-8 -*-
from odoo import models


class WcConnectionMixin(models.AbstractModel):
    _name = 'wc.connection.mixin'
    _description = 'WooCommerce Connection Helper'

    def _get_wc_params(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'url': ICP.get_param('wc_base_connector.wc_url', ''),
            'username': ICP.get_param('wc_base_connector.wc_username', ''),
            'password': ICP.get_param('wc_base_connector.wc_password', ''),
        }

    def _get_wc_auth(self):
        p = self._get_wc_params()
        return p['url'], (p['username'], p['password'].replace(' ', ''))
