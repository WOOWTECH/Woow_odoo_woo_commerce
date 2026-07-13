# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wc_order_id = fields.Integer(string="WC Order ID", index=True, copy=False)
    wc_order_status = fields.Char(string="WC Order Status", copy=False)
    wc_payment_method = fields.Char(string="WC Payment Method", copy=False)
