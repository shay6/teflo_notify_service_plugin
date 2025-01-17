# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Red Hat, Inc.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

"""
    tests.test_notify_service_plugin.py

    Unit tests for testing notify_service_plugin

    :copyright: (c) 2021 Red Hat, Inc.
    :license: GPLv3, see LICENSE for more details.
"""


import pytest
import mock
import json
import os
from teflo_notify_service_plugin import NotifyServicePlugin
from teflo.resources import Notification, Scenario
from teflo.exceptions import TefloNotifierError
from teflo.utils.config import Config


@pytest.fixture()
def config():
    config_file = '../assets/teflo.cfg'
    os.environ['TEFLO_SETTINGS'] = config_file
    config = Config()
    config.load()
    return config


@pytest.fixture()
def scenario_resource(config):
    sc = Scenario(config=config, parameters={'name': 'test_scenario'})
    setattr(sc, 'passed_tasks', ['provision', 'execute'])
    setattr(sc, 'failed_tasks', ['report'])
    setattr(sc, 'overall_status', 0)
    return sc

@pytest.fixture()
def params():

    params = dict(
        description='description goes here.',
        notifier='notify_service',
        credential='notify_service',
        on_start=False,
        params={'message_bus_request_body': {'body': 'message1'}, 'target':'gchat,message_bus'}
    )
    return params


@pytest.fixture()
def notification(params, config, scenario_resource):
    note = Notification(name='notify1', parameters=params,  config=getattr(scenario_resource, 'config'))
    scenario_resource.add_notifications(note)
    note.scenario = scenario_resource
    return note

@pytest.fixture()
def notify_service_plugin(notification):
    ns_plugin = NotifyServicePlugin(notification)
    return ns_plugin


class TestNotifyServicePlugin(object):

    @staticmethod
    def test_notify_service_plugin(notification):
        assert notification.notifier.__plugin_name__ == NotifyServicePlugin.__plugin_name__

    @staticmethod
    def test_notify_when_message_bus_topic_not_provided(notify_service_plugin):
        with pytest.raises(TefloNotifierError):
            notify_service_plugin.notify()

    @staticmethod
    def test_notify_when_message_bus_topic_not_dict(notify_service_plugin):
        notify_service_plugin.params.update(
            {'message_bus_request_body': 'string1', 'message_bus_topic': 'topic1'})
        with pytest.raises(TefloNotifierError):
            notify_service_plugin.notify()

    @staticmethod
    def test_with_empty_target(notify_service_plugin):
        notify_service_plugin.params.update({'target': ''})
        with pytest.raises(TefloNotifierError) as ex:
            notify_service_plugin.notify()

        assert "At least one Target(gchat/email/slack/irs/message_bus) are required to send " \
               "notifications using the Notify Service" in ex.value.args

    @staticmethod
    def test_with_incorrect_target(notify_service_plugin):
        notify_service_plugin.params.update({'target': 'hello'})
        with pytest.raises(TefloNotifierError) as ex:
            notify_service_plugin.notify()
        assert "Unknown target value hello found.Target should be one or more of this list:" \
               " 'gchat,email,slack,irc,message_bus'"in ex.value.args

    @staticmethod
    def test_get_params_with_message_bus_request_body(notify_service_plugin):
        notify_service_plugin.params.update({'message_bus_topic': 'topic1'})
        results = notify_service_plugin.get_params()
        assert results['targets'] == {'target': 'gchat'}
        assert results['message_bus'] == {'message_bus_topic': 'topic1',
                                          'message_bus_request_body': {'body': 'message1'}}

    @staticmethod
    def test_get_params_with_no_message_bus_request_body(notify_service_plugin):
        notify_service_plugin.params.update({'message_bus_topic': 'topic1'})
        notify_service_plugin.params.update({'message_bus_request_body': None})
        results = notify_service_plugin.get_params()
        assert results['targets'] == {'target': 'gchat,message_bus', 'message_bus_topic': 'topic1'}

    @staticmethod
    @mock.patch('teflo_notify_service_plugin.NotifyServicePlugin.api_call')
    def test_with_wrong_template_name(mock, notify_service_plugin):
        mock.return_value = None
        notify_service_plugin.params.update({'gchat_template_name': 'gchat1'})
        with pytest.raises(TefloNotifierError) as ex:
            notify_service_plugin.check_for_template(notify_service_plugin.params['gchat_template_name'])
        assert "Error finding template %s .error " in ex.value.args

    @staticmethod
    def test_generate_multi_api_payload_when_msgbody_not_provided(notify_service_plugin):
        result = json.loads(notify_service_plugin.generate_multi_api_payload())
        assert result['body']['passed_tasks'] == 'provision,execute'
        assert result['body']['failed_tasks'] == 'report'

    @staticmethod
    def test_generate_multi_api_payload_when_msgbody_is_string(notification):
        setattr(notification, 'message_body', 'this is message body')
        ns_plugin = NotifyServicePlugin(notification)
        result = json.loads(ns_plugin.generate_multi_api_payload())
        assert result == {'text': 'this is message body'}

    @staticmethod
    def test_generate_multi_api_payload_when_msgbody_is_dict(notification):
        setattr(notification, 'message_body', {'body': 'hello teflo user'})
        ns_plugin = NotifyServicePlugin(notification)
        result = json.loads(ns_plugin.generate_multi_api_payload())
        assert result == {'body': 'hello teflo user'}

    @staticmethod
    def test_generate_multi_api_payload_when_msgbody_is_incorrect(notification):
        setattr(notification, 'message_body', ['body', 'hello teflo user'])
        ns_plugin = NotifyServicePlugin(notification)
        with pytest.raises(TefloNotifierError) as ex:
            json.loads(ns_plugin.generate_multi_api_payload())
        assert "The body needs to be in a dictionary or string format ['body', 'hello teflo user'] " in ex.value.args
