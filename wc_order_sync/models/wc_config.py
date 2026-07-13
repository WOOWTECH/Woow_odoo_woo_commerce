# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    wc_webhook_secret = fields.Char(
        string="Webhook Secret",
        config_parameter='wc_order_sync.wc_webhook_secret',
    )
    wc_auto_confirm = fields.Boolean(
        string="Auto-confirm Orders",
        config_parameter='wc_order_sync.wc_auto_confirm',
        default=True,
    )
    wc_auto_stock = fields.Boolean(
        string="Auto-deduct Stock",
        config_parameter='wc_order_sync.wc_auto_stock',
        default=True,
        help="Automatically validate delivery orders for completed WC orders to deduct stock",
    )
    wc_default_product_id = fields.Many2one(
        'product.product',
        string="Default Product",
        config_parameter='wc_order_sync.wc_default_product_id',
        help="Fallback product when WC product cannot be matched",
    )

    def action_manual_sync(self):
        self.env['wc.sync.queue'].sudo()._cron_process_queue()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WooCommerce',
                'message': 'Manual sync completed',
                'type': 'success',
                'sticky': False,
            }
        }
