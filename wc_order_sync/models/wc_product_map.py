# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductWcMap(models.Model):
    _name = 'product.wc.map'
    _description = 'WooCommerce Product Mapping'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'wc_product_name'

    wc_product_name = fields.Char(string="WC Product Name", required=True, index=True, tracking=True)
    wc_product_id = fields.Integer(string="WC Product ID", index=True, tracking=True)
    product_id = fields.Many2one('product.product', string="Odoo Product",
                                 ondelete='set null', tracking=True)
    auto_matched = fields.Boolean(string="Auto Matched", default=False, tracking=True)
