# -*- coding: utf-8 -*-
import json
import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class WcSyncQueue(models.Model):
    _name = 'wc.sync.queue'
    _description = 'WooCommerce Sync Queue'
    _order = 'create_date desc'

    wc_order_id = fields.Integer(string="WC Order ID", index=True)
    wc_order_number = fields.Char(string="WC Order Number")
    payload = fields.Text(string="JSON Payload")
    state = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], default='pending', string="State", index=True)
    error_message = fields.Text(string="Error Message")
    sale_order_id = fields.Many2one('sale.order', string="Sale Order")
    partner_id = fields.Many2one('res.partner', string="Customer")
    attempts = fields.Integer(default=0, string="Attempts")
    wc_total = fields.Float(string="WC Order Amount")
    wc_date = fields.Char(string="WC Order Date")
    wc_status = fields.Char(string="WC Order Status")

    def action_retry(self):
        self.write({'state': 'pending', 'error_message': False, 'attempts': 0})

    @api.model
    def action_manual_sync(self):
        self._cron_process_queue()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'WooCommerce Sync',
                'message': 'Manual sync completed',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def _cron_process_queue(self):
        pending = self.search([
            ('state', '=', 'pending'),
            ('attempts', '<', 5),
        ], limit=50, order='create_date asc')
        _logger.info("WC Sync: Processing %d pending queue items", len(pending))
        for item in pending:
            try:
                item.write({'state': 'processing', 'attempts': item.attempts + 1})
                self.env.cr.commit()
                order_data = json.loads(item.payload)
                sale_order = self._process_wc_order(order_data, item)
                item.write({
                    'state': 'done',
                    'sale_order_id': sale_order.id if sale_order else False,
                    'partner_id': sale_order.partner_id.id if sale_order else False,
                    'error_message': False,
                })
                self.env.cr.commit()
            except Exception as e:
                self.env.cr.rollback()
                _logger.exception("WC Sync: Error processing queue item %d", item.id)
                item.write({'state': 'error', 'error_message': str(e)[:500]})
                self.env.cr.commit()

    def _process_wc_order(self, data, queue_item):
        wc_order_id = data.get('id')
        existing = self.env['sale.order'].sudo().search([('wc_order_id', '=', wc_order_id)], limit=1)
        if existing:
            return existing
        wc_date = self._parse_wc_date(data.get('date_created', ''))
        partner = self._find_or_create_partner(data, wc_date)
        order_lines = self._build_order_lines(data)
        order_vals = {
            'partner_id': partner.id,
            'wc_order_id': wc_order_id,
            'wc_order_status': data.get('status', ''),
            'wc_payment_method': data.get('payment_method_title', ''),
            'date_order': wc_date,
            'order_line': order_lines,
            'note': self._build_note(data),
        }
        pricelist = self.env['product.pricelist'].sudo().search([('currency_id.name', '=', 'TWD')], limit=1)
        if pricelist:
            order_vals['pricelist_id'] = pricelist.id
        sale_order = self.env['sale.order'].sudo().create(order_vals)
        ICP = self.env['ir.config_parameter'].sudo()
        auto_confirm = ICP.get_param('wc_order_sync.wc_auto_confirm', 'True')
        if auto_confirm in ('True', '1', 'true'):
            try:
                sale_order.action_confirm()
                # Restore the original WC order date (action_confirm resets it)
                sale_order.write({'date_order': wc_date})
            except Exception as e:
                _logger.warning("WC Sync: Auto-confirm failed for %s: %s", sale_order.name, str(e)[:100])
        wc_status = data.get('status', '')
        auto_stock = ICP.get_param('wc_order_sync.wc_auto_stock', 'True')
        if wc_status == 'completed' and auto_stock in ('True', '1', 'true'):
            self._auto_validate_pickings(sale_order)
        return sale_order

    def _auto_validate_pickings(self, sale_order):
        for picking in sale_order.picking_ids:
            if picking.state in ('confirmed', 'assigned', 'waiting'):
                try:
                    for move in picking.move_ids:
                        move.quantity = move.product_uom_qty
                    picking.with_context(skip_sms=True, skip_backorder=True).button_validate()
                except Exception as e:
                    _logger.warning("WC Sync: Auto-validate picking failed for %s: %s", sale_order.name, str(e)[:100])

    def _find_or_create_partner(self, data, wc_date=None):
        Partner = self.env['res.partner'].sudo()
        PartnerMap = self.env['partner.wc.map'].sudo()
        billing = data.get('billing', {})
        email = billing.get('email', '').strip()
        phone = billing.get('phone', '').strip()
        last_name = billing.get('last_name', '').strip()
        first_name = billing.get('first_name', '').strip()
        name = f"{last_name}{first_name}".strip() or email or 'Unknown Customer'
        wc_customer_id = data.get('customer_id', 0)
        order_date = wc_date or fields.Datetime.now()
        if wc_customer_id:
            mapping = PartnerMap.search([('wc_customer_id', '=', wc_customer_id)], limit=1)
            if mapping and mapping.partner_id:
                if not mapping.last_order_date or str(order_date) > str(mapping.last_order_date):
                    mapping.write({'last_order_date': order_date})
                return mapping.partner_id
        if email:
            mapping = PartnerMap.search([('wc_email', '=', email)], limit=1)
            if mapping and mapping.partner_id:
                if not mapping.last_order_date or str(order_date) > str(mapping.last_order_date):
                    mapping.write({'last_order_date': order_date})
                return mapping.partner_id
        partner = False
        if email:
            partner = Partner.search([('email', '=', email)], limit=1)
        if not partner and phone:
            partner = Partner.search(['|', ('phone', '=', phone), ('mobile', '=', phone)], limit=1)
        if not partner and name and name != 'Unknown Customer':
            partner = Partner.search([('name', '=', name), ('customer_rank', '>', 0)], limit=1)
        if not partner:
            country_tw = self.env['res.country'].sudo().search([('code', '=', 'TW')], limit=1)
            customer_tag = self.env['res.partner.category'].sudo().search([('name', '=', 'Customer')], limit=1)
            if not customer_tag:
                customer_tag = self.env['res.partner.category'].sudo().search([('name', 'ilike', 'customer')], limit=1)
            vals = {
                'name': name, 'email': email or False, 'phone': phone or False,
                'customer_rank': 1, 'lang': 'zh_TW', 'tz': 'Asia/Taipei',
                'country_id': country_tw.id if country_tw else False,
            }
            if customer_tag:
                vals['category_id'] = [(4, customer_tag.id)]
            street_parts = [billing.get(k) for k in ('address_1', 'address_2') if billing.get(k)]
            if street_parts:
                vals['street'] = ' '.join(street_parts)
            if billing.get('city'):
                vals['city'] = billing['city']
            if billing.get('postcode'):
                vals['zip'] = billing['postcode']
            partner = Partner.create(vals)
        existing_map = PartnerMap.search([
            '|', ('wc_customer_id', '=', wc_customer_id), ('wc_email', '=', email),
        ], limit=1) if (wc_customer_id or email) else False
        if existing_map:
            existing_map.write({'partner_id': partner.id, 'last_order_date': order_date})
        else:
            PartnerMap.create({
                'wc_customer_name': name, 'wc_customer_id': wc_customer_id,
                'wc_email': email, 'wc_phone': phone, 'partner_id': partner.id,
                'auto_matched': True, 'last_order_date': order_date,
            })
        return partner

    def _build_order_lines(self, data):
        lines = []
        ProductMap = self.env['product.wc.map'].sudo()
        ICP = self.env['ir.config_parameter'].sudo()
        default_product_id = int(ICP.get_param('wc_order_sync.wc_default_product_id', '0'))
        for item in data.get('line_items', []):
            wc_name = item.get('name', '')
            wc_product_id = item.get('product_id', 0)
            qty = item.get('quantity', 1)
            total = float(item.get('total', 0))
            price_unit = total / qty if qty else total
            product = False
            mapping = ProductMap.search([
                '|', ('wc_product_id', '=', wc_product_id), ('wc_product_name', '=', wc_name),
            ], limit=1)
            if mapping and mapping.product_id:
                product = mapping.product_id
            else:
                product = self._fuzzy_match_product(wc_name)
                if product:
                    ProductMap.create({
                        'wc_product_name': wc_name, 'wc_product_id': wc_product_id,
                        'product_id': product.id, 'auto_matched': True,
                    })
            if not product and default_product_id:
                product = self.env['product.product'].sudo().browse(default_product_id)
                if not product.exists():
                    product = False
            if not product:
                product = self.env['product.product'].sudo().create({
                    'name': wc_name[:100], 'type': 'service', 'sale_ok': True, 'list_price': price_unit,
                })
                ProductMap.create({
                    'wc_product_name': wc_name, 'wc_product_id': wc_product_id,
                    'product_id': product.id, 'auto_matched': True,
                })
            lines.append((0, 0, {
                'product_id': product.id, 'product_uom_qty': qty,
                'price_unit': price_unit, 'name': wc_name,
            }))
        return lines

    def _fuzzy_match_product(self, wc_name):
        Product = self.env['product.product'].sudo()
        if not wc_name:
            return False
        product = Product.search([('name', '=', wc_name)], limit=1)
        if product:
            return product
        products = Product.search([('sale_ok', '=', True)], limit=500)
        for p in products:
            if p.name and len(p.name) > 3 and p.name in wc_name:
                return p
        return False

    def _parse_wc_date(self, date_str):
        if not date_str:
            return fields.Datetime.now()
        try:
            return date_str.replace('T', ' ')[:19]
        except Exception:
            return fields.Datetime.now()

    def _build_note(self, data):
        parts = []
        if data.get('payment_method_title'):
            parts.append(f"Payment: {data['payment_method_title']}")
        if data.get('id'):
            parts.append(f"WC Order #{data['id']}")
        if data.get('customer_note'):
            parts.append(f"Note: {data['customer_note']}")
        for coupon in data.get('coupon_lines', []):
            parts.append(f"Coupon: {coupon.get('code', '')}")
        return '\n'.join(parts) if parts else ''
