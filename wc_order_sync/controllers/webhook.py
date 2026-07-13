# -*- coding: utf-8 -*-
import hashlib
import hmac
import json
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class WcWebhookController(http.Controller):

    @http.route('/wc_sync/webhook', type='json', auth='none',
                methods=['POST'], csrf=False)
    def receive_webhook(self):
        """Receive WooCommerce webhook and queue for processing."""
        try:
            body = request.httprequest.get_data(as_text=True)
            headers = request.httprequest.headers

            # Verify signature if secret is configured
            secret = request.env['ir.config_parameter'].sudo().get_param(
                'wc_order_sync.wc_webhook_secret', '')
            if secret:
                signature = headers.get('X-WC-Webhook-Signature', '')
                expected = hmac.new(
                    secret.encode('utf-8'),
                    body.encode('utf-8'),
                    hashlib.sha256,
                ).digest()
                import base64
                expected_b64 = base64.b64encode(expected).decode('utf-8')
                if not hmac.compare_digest(signature, expected_b64):
                    _logger.warning("WC Webhook: Invalid signature")
                    return {'status': 'error', 'message': 'invalid signature'}

            data = json.loads(body)

            # Skip ping/test webhooks
            topic = headers.get('X-WC-Webhook-Topic', '')
            if not data.get('id') or topic == 'action.woocommerce_webhook_delivery':
                _logger.info("WC Webhook: Ping received, topic=%s", topic)
                return {'status': 'ok', 'message': 'ping acknowledged'}

            wc_order_id = data.get('id')
            wc_status = data.get('status', '')

            # Only process completed/processing/on-hold orders
            if wc_status not in ('completed', 'processing', 'on-hold', ''):
                _logger.info("WC Webhook: Skipping order #%s status=%s",
                             wc_order_id, wc_status)
                return {'status': 'skipped', 'message': f'status {wc_status}'}

            # Check if already queued
            Queue = request.env['wc.sync.queue'].sudo()
            existing = Queue.search([
                ('wc_order_id', '=', wc_order_id),
                ('state', 'in', ('pending', 'processing', 'done')),
            ], limit=1)
            if existing:
                _logger.info("WC Webhook: Order #%s already in queue (%s)",
                             wc_order_id, existing.state)
                return {'status': 'duplicate', 'queue_id': existing.id}

            # Create queue item
            queue_item = Queue.create({
                'wc_order_id': wc_order_id,
                'wc_order_number': str(data.get('number', wc_order_id)),
                'payload': body,
                'state': 'pending',
                'wc_total': float(data.get('total', 0)),
                'wc_date': data.get('date_created', ''),
                'wc_status': wc_status,
            })

            _logger.info("WC Webhook: Queued order #%s (queue_id=%d)",
                         wc_order_id, queue_item.id)
            return {'status': 'queued', 'queue_id': queue_item.id}

        except Exception as e:
            _logger.exception("WC Webhook: Error processing webhook")
            return {'status': 'error', 'message': str(e)[:200]}

    @http.route('/wc_sync/health', type='http', auth='none',
                methods=['GET'], csrf=False)
    def health_check(self):
        """Health check endpoint for monitoring."""
        Queue = request.env['wc.sync.queue'].sudo()
        pending = Queue.search_count([('state', '=', 'pending')])
        errors = Queue.search_count([('state', '=', 'error')])
        done = Queue.search_count([('state', '=', 'done')])
        return json.dumps({
            'status': 'ok',
            'queue': {'pending': pending, 'errors': errors, 'done': done},
        })
