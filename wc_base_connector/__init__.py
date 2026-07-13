from . import models


def _migrate_config_keys(env):
    """Migrate config keys from wc_order_sync to wc_base_connector."""
    ICP = env['ir.config_parameter'].sudo()
    migrations = {
        'wc_order_sync.wc_url': 'wc_base_connector.wc_url',
        'wc_order_sync.wc_username': 'wc_base_connector.wc_username',
        'wc_order_sync.wc_password': 'wc_base_connector.wc_password',
    }
    for old_key, new_key in migrations.items():
        old_val = ICP.get_param(old_key, '')
        if old_val and not ICP.get_param(new_key, ''):
            ICP.set_param(new_key, old_val)
