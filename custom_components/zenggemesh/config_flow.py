"""Config flow for Zengge MESH lights"""

from typing import Mapping, Optional
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_COUNTRY,
)

from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import DOMAIN, CONF_MESH_NAME, CONF_MESH_PASSWORD, CONF_MESH_KEY
from .zengge_connect import ZenggeConnect

_LOGGER = logging.getLogger(__name__)


class ZenggeMeshFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Zengge config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        self._mesh_info: Optional[Mapping] = None

    async def async_step_user(self, user_input: Optional[Mapping] = None):
        """Handle the initial user step."""
        if self._mesh_info is None:
            return await self.async_step_zengge_connect()

        _LOGGER.debug("async_step_user: user_input: %s", user_input)
        if user_input is not None and user_input.get('mac'):
            await self.async_set_unique_id(
                self._mesh_info.get(CONF_MESH_NAME), raise_on_progress=False
            )
            return await self._async_create_entry_from_discovery(
                user_input.get('mac'),
                user_input.get('name'),
                self._mesh_info.get(CONF_MESH_NAME),
                self._mesh_info.get(CONF_MESH_PASSWORD),
                self._mesh_info.get(CONF_MESH_KEY)
            )

        data_schema = vol.Schema(
            {
                vol.Required("mac"): str,
                vol.Required("name", description={"suggested_value": "Zengge light"}): str,
            }
        )
        return self.async_show_form(
            step_id="manual",
            data_schema=data_schema,
        )

    async def async_step_zengge_connect(self, user_input: Optional[Mapping] = None):

        errors = {}
        username: str = ''
        password: str = ''
        country: str = ''
        typeStr: str = ''
        zengge_connect = None


        if user_input is not None:
            username = user_input.get(CONF_USERNAME)
            password = user_input.get(CONF_PASSWORD)
            _LOGGER.info('Before Country')
            country = user_input.get(CONF_COUNTRY)
            _LOGGER.info('Country: [%s]', country)

        if username and password and country:
            try:
                zengge_connect = ZenggeConnect(username, password, country)
                await zengge_connect.login()
            except Exception as e:
                _LOGGER.error('Can not login to Zengge cloud [%s]', e)
                errors[CONF_PASSWORD] = 'cannot_connect'

        if user_input is None or zengge_connect is None or errors:
            return self.async_show_form(
                step_id="zengge_connect",
                data_schema=vol.Schema({
                    vol.Required(CONF_USERNAME, default=username): str,
                    vol.Required(CONF_PASSWORD, default=password): str,
                    vol.Required(CONF_COUNTRY): SelectSelector(
                        SelectSelectorConfig(
                            mode=SelectSelectorMode.DROPDOWN, options=['AU','AL','CN','GB','ES','FR','DE','IT','JP','RU','US']
                        )
                    ),
                }),
                errors=errors,
            )

        devices = []
        for device in await zengge_connect.devices():
            _LOGGER.debug('Processing device - %s', device)
            if 'wiringType' in device:
                if device['wiringType'] == 0:
                    _LOGGER.warning('Skipped device, wiringType of 0 - %s', device)
                    continue
            if 'deviceType' not in device:
                _LOGGER.warning('Skipped device, missing deviceType - %s', device)
                continue
            if 'meshAddress' not in device or not device['meshAddress']:
                _LOGGER.warning('Skipped device, missing meshAddress - %s', device)
                continue
            if 'macAddress' not in device:
                _LOGGER.warning('Skipped device, missing macAddress - %s', device)
                continue
            if 'displayName' not in device:
                _LOGGER.warning('Skipped device, missing displayName - %s', device)
                continue

            if 'modelName' not in device:
                device['modelName'] = 'unknown'
            if 'vendor' not in device:
                device['vendor'] = 'unknown'
            if 'firmwareRevision' not in device:
                device['firmwareRevision'] = 'unknown'
            if 'versionNum' not in device:
                device['versionNum'] = None
            if device['deviceType'] == 65:
                typeStr = 'light|color|temperature|dimming'
            else:
                _LOGGER.warning('deviceType #: %s', device['deviceType'])
                typeStr = 'light|color|temperature|dimming'

            devices.append({
                'mesh_id': int(device['meshAddress']),
                'name': device['displayName'],
                'mac': device['macAddress'],
                'model': device['modelName'],
                'manufacturer': device['vendor'],
                'firmware': device['firmwareRevision'],
                'hardware': device['versionNum'],
                'type': typeStr
            })

        if len(devices) == 0:
            return self.async_abort(reason="no_devices_found")

        credentials = await zengge_connect.credentials()

        data = {
            CONF_MESH_NAME: credentials['meshKey'],
            CONF_MESH_PASSWORD: credentials['meshPassword'],
            CONF_MESH_KEY: credentials['meshLTK'],
            # 'zengge_connect': {
            #     CONF_USERNAME: user_input[CONF_USERNAME],
            #     CONF_PASSWORD: user_input[CONF_PASSWORD]
            # },
            'devices': devices
        }

        return self.async_create_entry(title='Zengge Cloud', data=data)

    async def async_step_mesh_info(self, user_input: Optional[Mapping] = None):

        _LOGGER.debug("async_step_mesh_info: user_input: %s", user_input)

        errors = {}
        name: str = ''
        password: str = ''
        key: str = ''

        if user_input is not None:
            name = user_input.get(CONF_MESH_NAME)
            password = user_input.get(CONF_MESH_PASSWORD)
            key = user_input.get(CONF_MESH_KEY)

            if len(user_input.get(CONF_MESH_NAME)) > 16:
                errors[CONF_MESH_NAME] = 'max_length_16'
            if len(user_input.get(CONF_MESH_PASSWORD)) > 16:
                errors[CONF_MESH_PASSWORD] = 'max_length_16'
            if len(user_input.get(CONF_MESH_KEY)) > 16:
                errors[CONF_MESH_KEY] = 'max_length_16'

        if user_input is None or errors:
            return self.async_show_form(
                step_id="mesh_info",
                data_schema=vol.Schema({
                    vol.Required(CONF_MESH_NAME, default=name): str,
                    vol.Required(CONF_MESH_PASSWORD, default=password): str,
                    vol.Required(CONF_MESH_KEY, default=key): str
                }),
                errors=errors,
            )

        self._mesh_info = user_input
        return await self.async_step_user()

    async def async_step_manual(self, user_input: Optional[Mapping] = None):
        """Forward result of manual input form to step user"""
        return await self.async_step_user(user_input)

    async def _async_create_entry_from_discovery(
            self,
            mac: str,
            name: str,
            mesh_name: str,
            mesh_pass: str,
            mesh_key: str
    ):
        """Create an entry from discovery."""
        _LOGGER.debug(
            "_async_create_entry_from_discovery: device: %s [%s]",
            name,
            mac
        )

        data = {
            CONF_MESH_NAME: mesh_name,
            CONF_MESH_PASSWORD: mesh_pass,
            CONF_MESH_KEY: mesh_key,
            'devices': [
                {
                    'mesh_id': 0,
                    'mac': mac,
                    'name': name,
                    'model': 'unknown',
                    'manufacturer': 'Zengge',
                    'firmware': 'unknown',
                    'type': 'light|color|temperature|dimming',
                }
            ]
        }

        return self.async_create_entry(title=name, data=data)
