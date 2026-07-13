# -*- coding: utf-8 -*-
from odoo import fields, models


class PartnerWcMap(models.Model):
    _name = 'partner.wc.map'
    _description = 'WooCommerce Partner Mapping'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'wc_customer_name'

    wc_customer_name = fields.Char(string="WC Customer Name", required=True, index=True, tracking=True)
    wc_customer_id = fields.Integer(string="WC Customer ID", index=True, tracking=True)
    wc_email = fields.Char(string="WC Email", tracking=True)
    wc_phone = fields.Char(string="WC Phone", tracking=True)
    partner_id = fields.Many2one('res.partner', string="Odoo Contact",
                                 ondelete='set null', tracking=True)
    auto_matched = fields.Boolean(string="Auto Matched", default=False, tracking=True)
    last_order_date = fields.Datetime(string="Last Order Date")
    order_count = fields.Integer(string="Order Count", compute='_compute_order_count')

    def _compute_order_count(self):
        for rec in self:
            if rec.partner_id:
                rec.order_count = self.env['sale.order'].sudo().search_count([
                    ('partner_id', '=', rec.partner_id.id),
                    ('wc_order_id', '>', 0),
                ])
            else:
                rec.order_count = 0
