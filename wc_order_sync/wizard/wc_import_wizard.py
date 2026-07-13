# -*- coding: utf-8 -*-
import json
import logging
import requests
from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class WcImportWizard(models.TransientModel):
    _name = 'wc.import.wizard'
    _description = 'WooCommerce Historical Order Import'

    date_from = fields.Date(string="Start Date")
    date_to = fields.Date(string="End Date")
    status_filter = fields.Selection([
        ('completed', 'Completed'),
        ('processing', 'Processing'),
        ('any', 'All'),
    ], default='completed', string="Order Status")
    import_limit = fields.Integer(string="Import Limit", default=100,
                                  help="0 = unlimited")
    imported_count = fields.Integer(string="Imported", readonly=True)
    skipped_count = fields.Integer(string="Skipped (Duplicate)", readonly=True)
    error_count = fields.Integer(string="Errors", readonly=True)
    state = fields.Selection([
        ('draft', 'Setup'),
        ('done', 'Done'),
    ], default='draft')

    def action_import(self):
        mixin = self.env['wc.connection.mixin'].sudo()
        wc_url, auth = mixin._get_wc_auth()
        if not wc_url or not auth[0]:
            raise UserError("Please fill in WooCommerce connection settings first")
        api_url = f"{wc_url.rstrip('/')}/wp-json/wc/v3/orders"
        Queue = self.env['wc.sync.queue'].sudo()
        imported = 0
        skipped = 0
        errors = 0
        page = 1
        per_page = 100
        limit = self.import_limit or 999999
        while imported + skipped < limit:
            params = {
                'per_page': min(per_page, limit - imported - skipped),
                'page': page, 'orderby': 'date', 'order': 'asc',
            }
            if self.status_filter and self.status_filter != 'any':
                params['status'] = self.status_filter
            if self.date_from:
                params['after'] = f"{self.date_from}T00:00:00"
            if self.date_to:
                params['before'] = f"{self.date_to}T23:59:59"
            try:
                resp = requests.get(api_url, auth=auth, params=params, timeout=30)
                if resp.status_code != 200:
                    errors += 1
                    break
                orders = resp.json()
                if not orders:
                    break
                for order_data in orders:
                    wc_id = order_data.get('id')
                    if Queue.search([('wc_order_id', '=', wc_id)], limit=1) or \
                       self.env['sale.order'].sudo().search([('wc_order_id', '=', wc_id)], limit=1):
                        skipped += 1
                        continue
                    Queue.create({
                        'wc_order_id': wc_id,
                        'wc_order_number': str(order_data.get('number', wc_id)),
                        'payload': json.dumps(order_data),
                        'state': 'pending',
                        'wc_total': float(order_data.get('total', 0)),
                        'wc_date': order_data.get('date_created', ''),
                        'wc_status': order_data.get('status', ''),
                    })
                    imported += 1
                    if imported + skipped >= limit:
                        break
                page += 1
                if page > int(resp.headers.get('X-WP-TotalPages', 1)):
                    break
            except requests.RequestException:
                errors += 1
                break
        self.write({'imported_count': imported, 'skipped_count': skipped, 'error_count': errors, 'state': 'done'})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form', 'target': 'new'}
