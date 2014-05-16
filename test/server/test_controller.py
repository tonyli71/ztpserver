#
# Copyright (c) 2014, Arista Networks, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name of Arista Networks nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL ARISTA NETWORKS
# BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR
# BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE
# OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN
# IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
# pylint: disable=C0102,C0103,E1103,W0142,W0613
#

import unittest
import json

from webob import Request

from mock import Mock, patch

import ztpserver.neighbordb
import ztpserver.topology
import ztpserver.controller
import ztpserver.config

from ztpserver.app import enable_handler_console
from ztpserver.repository import FileObjectNotFound
from ztpserver.serializers import SerializerError

from server_test_lib import remove_all, random_string
from server_test_lib import ztp_headers, write_file
from server_test_lib import create_definition, create_attributes, create_node
from server_test_lib import create_bootstrap_conf

@patch('ztpserver.controller.create_filestore')
class RouterUnitTests(unittest.TestCase):

    def match_routes(self, url, valid, invalid):

        request = Request.blank(url)
        router = ztpserver.controller.Router()

        if valid:
            for method in valid.split(','):
                request.method = method
                msg = 'method %s failed for url %s' % (method, url)
                self.assertIsNotNone(router.map.match(environ=request.environ),
                                     msg)

        if invalid:
            for method in invalid.split(','):
                request.method = method
                msg = 'method %s failed for url %s' % (method, url)
                self.assertIsNone(router.map.match(environ=request.environ),
                                  msg)

    def test_bootstrap_collection(self, filestore):
        url = '/bootstrap'
        self.match_routes(url, 'GET', 'POST,PUT,DELETE')

    def test_bootstrap_resource(self, filestore):
        url = '/bootstrap/%s' % random_string()
        self.match_routes(url, None, 'GET,POST,PUT,DELETE')

    def test_files_collection(self, filestore):
        url = '/files'
        self.match_routes(url, None, 'GET,POST,PUT,DELETE')

    def test_files_resource(self, filestore):
        url = '/files/%s' % random_string()
        self.match_routes(url, 'GET', 'POST,PUT,DELETE')

        url = '/files/%s/%s' % (random_string(), random_string())
        self.match_routes(url, 'GET', 'POST,PUT,DELETE')

    def test_actions_collection(self, filestore):
        url = '/actions'
        self.match_routes(url, None, 'GET,POST,PUT,DELETE')

    def test_actions_resource(self, filestore):
        url = '/actions/%s' % random_string()
        self.match_routes(url, 'GET', 'POST,PUT,DELETE')

    def test_nodes_collection(self, filestore):
        url = '/nodes'
        self.match_routes(url, 'POST', 'GET,PUT,DELETE')

    def test_nodes_resource(self, filestore):
        url = '/nodes/%s' % random_string()
        self.match_routes(url, 'GET', 'POST,PUT,DELETE')

    def test_nodes_resource_get_config(self, filestore):
        url = '/nodes/%s/startup-config' % random_string()
        self.match_routes(url, 'GET,PUT', 'POST,DELETE')


@patch('ztpserver.controller.create_filestore')
class BootstrapControllerUnitTests(unittest.TestCase):


    def test_get_bootstrap_success(self, filestore):
        filestore.return_value.get_file.return_value = \
            Mock(contents=random_string())
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.BootstrapController()
        resp = controller.get_bootstrap()

        contents = filestore.return_value.get_file.return_value.contents
        self.assertEqual(resp, contents)

    def test_get_bootstrap_failure(self, filestore):
        filestore.return_value.get_file = Mock(side_effect=FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.BootstrapController()
        self.assertRaises(FileObjectNotFound, controller.get_bootstrap)

    def test_get_config_success(self, filestore):
        conf_file = create_bootstrap_conf()
        conf_file.add_logging(dict(destination=random_string(),
                                   level=random_string()))

        filestore.return_value.get_file.return_value = \
            Mock(contents=conf_file.as_yaml())
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.BootstrapController()
        resp = controller.get_config()

        self.assertEqual(resp, conf_file.as_dict())

    def test_get_config_defaults(self, filestore):
        filestore.return_value.get_file = \
            Mock(side_effect=ztpserver.repository.FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.BootstrapController()
        resp = controller.get_config()

        self.assertEqual(resp, dict(logging=list(), xmpp=dict()))

    def test_get_config_invalid_format(self, filestore):
        conf_file = """
            logging:
              - destination: null
              level: null
        """

        filestore.return_value.get_file.return_value = Mock(contents=conf_file)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.BootstrapController()
        self.assertRaises(SerializerError, controller.get_config)


@patch('ztpserver.controller.create_filestore')
class BootstrapControllerIntegrationTests(unittest.TestCase):

    def test_get_bootstrap(self, filestore):
        contents = random_string()

        filestore.return_value.get_file.return_value = Mock(contents=contents)
        ztpserver.controller.create_filestore = filestore

        request = Request.blank('/bootstrap', headers=ztp_headers())
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'text/x-python')
        self.assertEqual(resp.body, contents)

    def test_get_bootstrap_config_defaults(self, filestore):
        filestore.return_value.get_file = \
            Mock(side_effect=ztpserver.repository.FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        request = Request.blank('/bootstrap/config')
        resp = request.get_response(ztpserver.controller.Router())

        defaultconfig = {'logging': list(), 'xmpp': dict()}

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertEqual(json.loads(resp.body), json.dumps(defaultconfig))

    def test_get_bootstrap_config(self, filestore):
        logging = [dict(destination=random_string(), level=random_string())]
        xmpp = dict(username=random_string(), domain=random_string(),
                    password=random_string(), rooms=[random_string()])
        conf = dict(logging=logging, xmpp=xmpp)
        conf = json.dumps(conf)

        filestore.return_value.get_file.return_value.contents = conf
        ztpserver.controller.create_filestore = filestore

        request = Request.blank('/bootstrap/config', headers=ztp_headers())
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertEqual(json.loads(resp.body), conf)


@patch('ztpserver.controller.create_filestore')
class FilesControllerIntegrationTests(unittest.TestCase):

    def tearDown(self):
        remove_all()

    def test_get_file_success(self, filestore):
        contents = random_string()
        filepath = write_file(contents)

        filestore.return_value.get_file.return_value.name = filepath
        ztpserver.controller.create_filestore = filestore

        url = '/files/%s' % filepath
        request = Request.blank(url)
        resp = request.get_response(ztpserver.controller.Router())

        filestore.return_value.get_file.assert_called_with(filepath)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.body, contents)


    def test_get_missing_file(self, filestore):
        filestore.return_value.get_file = Mock(side_effect=\
            ztpserver.repository.FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        filename = random_string()
        url = '/files/%s' % filename

        request = Request.blank(url)
        resp = request.get_response(ztpserver.controller.Router())

        filestore.return_value.get_file.assert_called_with(filename)
        self.assertEqual(resp.status_code, 404)


@patch('ztpserver.controller.create_filestore')
class ActionsControllerIntegrationTests(unittest.TestCase):

    def test_get_action(self, filestore):
        file_mock = Mock(contents=random_string())
        filestore.return_value.get_file.return_value = file_mock
        ztpserver.controller.create_filestore = filestore

        filename = random_string()
        url = '/actions/%s' % filename

        request = Request.blank(url)
        resp = request.get_response(ztpserver.controller.Router())

        filestore.return_value.get_file.assert_called_with(filename)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'text/x-python')
        self.assertEqual(resp.body, file_mock.contents)

    def test_get_missing_action(self, filestore):
        filestore.return_value.get_file = Mock(side_effect=FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        filename = random_string()
        url = '/actions/%s' % filename

        request = Request.blank(url)
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 404)


@patch('ztpserver.controller.create_filestore')
class NodesControllerUnitTests(unittest.TestCase):

    def setUp(self):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', False, 'default')

    def test_load_node_success(self, filestore):
        node = create_node()

        filestore.return_value.get_file.return_value.contents = node.as_yaml()
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        resp = controller.load_node(node.systemmac)

        filepath = '%s/%s' % (node.systemmac, ztpserver.controller.NODE_FN)
        filestore.return_value.get_file.assert_called_with(filepath)

        self.assertIsInstance(resp, ztpserver.topology.Node)
        self.assertEqual(resp.serialize(), node.as_dict())

    def test_load_node_serializer_failure(self, filestore):
        node = """
            - systemmac: foo
            serialnumber: bar
        """

        filestore.return_value.get_file.return_value.contents = node
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        self.assertRaises(SerializerError, controller.load_node, None)

    def test_required_attributes_success(self, filestore):
        request = Mock(json={'systemmac': random_string()})
        response = dict()

        controller = ztpserver.controller.NodesController()
        resp = controller.required_attributes(response, request=request)

        self.assertEqual(resp, (dict(), 'node_exists'))

    def test_required_attributes_missing(self, filestore):
        controller = ztpserver.controller.NodesController()
        self.assertRaises(AttributeError, controller.required_attributes,
                          None, None)

    def test_node_exists_success(self, filestore):
        filestore.return_value.exists.return_value = True
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.node_exists(dict(), node=Mock())

        self.assertEqual(state, 'dump_node')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['status'], 409)

    def test_node_exists_definition_exists(self, filestore):
        node = create_node()

        def exists(filepath):
            if filepath.endswith(ztpserver.controller.DEFINITION_FN):
                return True
            return False

        filestore.return_value.exists = Mock(side_effect=exists)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.node_exists(dict(), node=node)

        self.assertEqual(state, 'dump_node')
        self.assertEqual(resp['status'], 409)

    def test_node_exists_startup_config_exists(self, filestore):
        node = create_node()

        def exists(filepath):
            if filepath.endswith(ztpserver.controller.STARTUP_CONFIG_FN):
                return True
            return False

        filestore.return_value.exists = Mock(side_effect=exists)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.node_exists(dict(), node=node)

        self.assertEqual(state, 'dump_node')
        self.assertEqual(resp['status'], 409)

    def test_node_exists_sysmac_folder_exists(self, filestore):
        node = create_node()

        def exists(filepath):
            if filepath.endswith(node.systemmac):
                return True
            return False

        filestore.return_value.exists = Mock(side_effect=exists)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.node_exists(dict(), node=node)

        self.assertEqual(state, 'post_config')
        self.assertTrue('status' not in resp)

    def test_node_exists_failure(self, filestore):
        filestore.return_value.exists.return_value = False
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.node_exists(dict(), node=Mock())

        self.assertEqual(state, 'post_config')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp, dict())

    def test_dump_node_success(self, filestore):
        ztpserver.controller.create_filestore = filestore

        node = create_node()
        attrs = "systemmac:\n    %s" % node.systemmac

        node = Mock(systemmac=node.systemmac)
        node.dumps.return_value = attrs

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.dump_node(dict(), node=node)

        filepath = '%s/%s' % (node.systemmac, ztpserver.controller.NODE_FN)
        filestore.return_value.write_file.assert_called_with(filepath, attrs)

        self.assertEqual(state, 'set_location')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp, dict())

    def test_dump_node_write_file_failure(self, filestore):
        filestore.return_value.write_file = Mock(side_effect=IOError)
        ztpserver.controller.create_filestore = filestore

        systemmac = random_string()
        node = Mock(systemmac=systemmac)

        controller = ztpserver.controller.NodesController()
        self.assertRaises(IOError, controller.dump_node, dict(), node=node)

    def test_set_location_success(self, filestore):
        node = Mock(systemmac=random_string())
        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.set_location(dict(), node=node)

        location = '/nodes/%s' % node.systemmac
        self.assertIsNone(state)
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['location'], location)

    def test_set_location_failure(self, filestore):
        controller = ztpserver.controller.NodesController()
        self.assertRaises(AttributeError, controller.set_location,
                          dict(), node=None)

    def test_post_config_success(self, filestore):
        request = Mock(json=dict(config=random_string()))
        controller = ztpserver.controller.NodesController()

        add_node_mock = Mock()
        controller.add_node = add_node_mock

        (resp, state) = controller.post_config(dict(), request=request,
                                               node=Mock())

        self.assertTrue(add_node_mock.called)
        self.assertEqual(state, 'set_location')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['status'], 201)

    def test_post_config_key_error_failure(self, filestore):
        request = Mock(json=dict())
        controller = ztpserver.controller.NodesController()

        add_node_mock = Mock()
        controller.add_node = add_node_mock

        (resp, state) = controller.post_config(dict(), request=request,
                                               node=Mock())

        self.assertFalse(add_node_mock.called)
        self.assertEqual(state, 'post_node')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp, dict())

    def test_post_config_failure(self, filestore):
        controller = ztpserver.controller.NodesController()
        add_node_mock = Mock(side_effect=Exception)
        controller.add_node = add_node_mock
        self.assertRaises(Exception, controller.post_config, dict())

    def test_post_node_success_single_match(self, filestore):
        request = Mock(json=dict(neighbors=dict()))
        node = Mock(systemmac=random_string())

        definitions = Mock()
        definitions.get_file.return_value.contents = random_string()

        pattern = Mock()
        pattern.dumps.return_value = random_string()

        ztpserver.neighbordb.topology.match_node = Mock(return_value=[pattern])

        controller = ztpserver.controller.NodesController()
        controller.definitions = definitions
        controller.add_node = Mock()

        (resp, state) = controller.post_node(dict(), request=request, node=node)

        assert controller.add_node.called
        assert controller.add_node.call_count == 1
        args = controller.add_node.call_args[0]

        self.assertEqual(args[0], node.systemmac)

        fn, value = args[1][0]
        self.assertEqual(fn, ztpserver.controller.DEFINITION_FN)
        self.assertEqual(value, definitions.get_file.return_value.contents)

        fn, value = args[1][1]
        self.assertEqual(fn, ztpserver.controller.PATTERN_FN)
        self.assertEqual(value, pattern.dumps.return_value)

        self.assertEqual(state, 'dump_node')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['status'], 201)

    def test_post_node_success_multiple_matches(self, filestore):
        request = Mock(json=dict(neighbors=dict()))
        node = Mock(systemmac=random_string())

        definitions = Mock()
        definitions.get_file.return_value.contents = random_string()

        pattern = Mock()
        pattern.dumps.return_value = random_string()

        matches = [pattern, Mock(), Mock()]
        ztpserver.neighbordb.topology.match_node = Mock(return_value=matches)

        controller = ztpserver.controller.NodesController()
        controller.definitions = definitions
        controller.add_node = Mock()

        (resp, state) = controller.post_node(dict(), request=request, node=node)

        assert controller.add_node.called
        assert controller.add_node.call_count == 1
        args = controller.add_node.call_args[0]

        self.assertEqual(args[0], node.systemmac)

        fn, value = args[1][0]
        self.assertEqual(fn, ztpserver.controller.DEFINITION_FN)
        self.assertEqual(value, definitions.get_file.return_value.contents)

        fn, value = args[1][1]
        self.assertEqual(fn, ztpserver.controller.PATTERN_FN)
        self.assertEqual(value, pattern.dumps.return_value)

        self.assertEqual(state, 'dump_node')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['status'], 201)

    def test_post_node_failure_no_neighbors(self, filestore):
        request = Mock(json=dict())
        node = Mock(systemmac=random_string())

        controller = ztpserver.controller.NodesController()
        self.assertRaises(AssertionError, controller.post_node, dict(),
                          request=request, node=node)

    def test_post_node_failure_no_matches(self, filestore):
        request = Mock(json=dict(neighbors=dict()))
        node = Mock(systemmac=random_string())

        ztpserver.neighbordb.topology.match_node = Mock(return_value=list())

        controller = ztpserver.controller.NodesController()
        self.assertRaises(AssertionError, controller.post_node, dict(),
                          request=request, node=node)

    def test_post_node_no_definition_in_pattern(self, filestore):
        request = Mock(json=dict(neighbors=dict()))
        node = Mock(systemmac=random_string())

        pattern = Mock()
        del pattern.definition

        ztpserver.neighbordb.topology.match_node = Mock()
        ztpserver.neighbordb.topology.match_node.return_value = [pattern]

        controller = ztpserver.controller.NodesController()
        self.assertRaises(AttributeError, controller.post_node, dict(),
                          request=request, node=node)

    def test_get_definition_success(self, filestore):
        node = create_node()
        definition = create_definition()

        filestore.return_value.get_file.return_value = \
            Mock(contents=definition.as_yaml())
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.get_definition(dict(),
                                                  resource=node.systemmac)

        filepath = '%s/%s' % (node.systemmac,
                              ztpserver.controller.DEFINITION_FN)
        filestore.return_value.get_file.assert_called_with(filepath)
        self.assertEqual(state, 'do_validation')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['definition'], definition.as_dict())

    def test_get_startup_config_success(self, filestore):
        resource = random_string()
        ztpserver.controller.create_filestore = filestore

        action_name = random_string()
        action = {'name': action_name, 'action': 'replace_config'}
        ztpserver.neighbordb.replace_config_action = Mock(return_value=action)

        definition = create_definition()
        definition.name = random_string()
        response = dict(definition=definition.as_dict())

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.get_startup_config(response,
                                                      resource=resource)

        self.assertEqual(state, 'do_actions')
        self.assertIsInstance(resp, dict)
        self.assertTrue(resp['get_startup_config'])
        self.assertTrue(resp['definition'], definition.name)
        self.assertEqual(resp['definition']['actions'][0]['name'], action_name)

    def test_get_startup_config_success_no_definition(self, filestore):
        resource = random_string()
        ztpserver.controller.create_filestore = filestore

        action_name = random_string()
        action = {'name': action_name, 'action': 'replace_config'}
        ztpserver.neighbordb.replace_config_action = Mock(return_value=action)

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.get_startup_config(dict(), resource=resource)

        self.assertEqual(state, 'do_actions')
        self.assertIsInstance(resp, dict)
        self.assertTrue(resp['get_startup_config'])
        self.assertTrue(resp['definition'], 'Autogenerated definition')
        self.assertEqual(resp['definition']['actions'][0]['name'], action_name)

    def test_get_definition_serializer_failure(self, filestore):
        systemmac = random_string()
        filestore.return_value.get_file.return_value = Mock(contents=None)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        self.assertRaises(SerializerError, controller.get_definition,
                          dict(), resource=systemmac)

    def test_do_validation_success(self, filestore):
        node = create_node()
        ztpserver.controller.create_filestore = filestore

        ztpserver.neighbordb.load_pattern = Mock(name='load_pattern6')
        cfg = {'return_value.match_node.return_value': True}
        ztpserver.neighbordb.load_pattern.configure_mock(**cfg)

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_validation(dict(),
                                                 resource=node.systemmac,
                                                 node=Mock())

        filepath = '%s/%s' % (node.systemmac, ztpserver.controller.PATTERN_FN)
        filestore.return_value.get_file.assert_called_with(filepath)

        self.assertEqual(state, 'get_startup_config')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp, dict())

    def test_do_validation_disabled_success(self, filestore):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', True, 'default')

        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_validation(dict())

        self.assertEqual(state, 'get_startup_config')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp, dict())

    def test_get_attributes_success(self, filestore):
        systemmac = random_string()
        contents = random_string()

        filestore.return_value.get_file.return_value = Mock(contents=contents)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.get_attributes(dict(), resource=systemmac)

        filepath = '%s/%s' % (systemmac, ztpserver.controller.ATTRIBUTES_FN)
        filestore.return_value.get_file.assert_called_with(filepath)
        self.assertEqual(state, 'do_substitution')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['attributes'], contents)

    def test_get_attributes_missing(self, filestore):
        node = create_node()

        filestore.return_value.exists.return_value = False
        filestore.return_value.get_file = \
            Mock(side_effect=ztpserver.repository.FileObjectNotFound)
        ztpserver.controller.create_filestore = filestore

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.get_attributes(dict(),
                                                  resource=node.systemmac)

        self.assertEqual(state, 'do_substitution')
        self.assertIsInstance(resp, dict)
        self.assertEqual(resp['attributes'], dict())

    def test_do_substitution_success(self, filestore):
        ztpserver.controller.create_filestore = filestore

        defattrs = dict(foo='$foo')

        definition = create_definition()
        definition.add_attribute('foo', 'bar')
        definition.add_action(name='dummy action', attributes=defattrs)

        response = dict(definition=definition.as_dict())

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_substitution(response)

        self.assertEqual(state, 'do_resources')
        self.assertIsInstance(resp, dict)

        foo = resp['definition']['actions'][0]['attributes']['foo']
        self.assertEqual(foo, 'bar')

    def test_do_substitution_with_attributes(self, filestore):
        ztpserver.controller.create_filestore = filestore

        defattrs = dict(foo='$foo')

        definition = create_definition()
        definition.add_attribute('foo', 'bar')
        definition.add_action(name='dummy action', attributes=defattrs)

        g_attr_foo = random_string()
        attributes = create_attributes()
        attributes.add_attribute('foo', g_attr_foo)

        response = dict(definition=definition.as_dict(),
                        attributes=attributes.as_dict())

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_substitution(response)

        self.assertEqual(state, 'do_resources')
        self.assertIsInstance(resp, dict)

        foo = resp['definition']['actions'][0]['attributes']['foo']
        self.assertEqual(foo, g_attr_foo)

    def test_do_resources_success(self, filestore):
        ztpserver.controller.create_filestore = filestore

        var_foo = random_string()
        ztpserver.neighbordb.resources = Mock(return_value=dict(foo=var_foo))

        definition = create_definition()
        definition.add_action(name='dummy action',
                              attributes=dict(foo=random_string()))

        response = dict(definition=definition.as_dict())

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_resources(response, node=Mock())

        self.assertEqual(state, 'finalize_response')
        self.assertIsInstance(resp, dict)
        foo = resp['definition']['actions'][0]['attributes']['foo']
        self.assertEqual(foo, var_foo)

    def test_do_put_config_success(self, filestore):
        ztpserver.controller.create_filestore = filestore

        resource = random_string()
        body = random_string()
        request = Mock(content_type='text/plain', body=body)

        controller = ztpserver.controller.NodesController()
        (resp, state) = controller.do_put_config(dict(), resource=resource,
                                                 request=request)

        filepath = '%s/%s' % (resource, ztpserver.controller.STARTUP_CONFIG_FN)
        filestore.return_value.write_file.called_with_args(filepath, body)
        self.assertIsNone(state)
        self.assertEqual(resp, dict())


    def test_do_put_config_invalid_content_type(self, filestore):
        ztpserver.controller.create_filestore = filestore

        resource = random_string()
        body = random_string()
        request = Mock(content_type='text/html', body=body)

        controller = ztpserver.controller.NodesController()
        self.assertRaises(AssertionError, controller.do_put_config, dict(),
                          resource=resource, request=request)

    def test_do_put_config_invalid_resource(self, filestore):
        filestore.return_value.write_file = Mock(side_effect=IOError)
        ztpserver.controller.create_filestore = filestore

        resource = random_string()
        body = random_string()
        request = Mock(content_type='text/plain', body=body)

        controller = ztpserver.controller.NodesController()
        self.assertRaises(IOError, controller.do_put_config, dict(),
                          resource=resource, request=request)

@patch('ztpserver.controller.create_filestore')
class NodesControllerPostFsmIntegrationTests(unittest.TestCase):

    def setUp(self):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', False, 'default')

    def test_missing_required_attributes(self, filestore):
        url = '/nodes'
        body = json.dumps(dict())

        ztpserver.controller.create_filestore = filestore

        request = Request.blank(url, body=body, method='POST',
                                headers=ztp_headers())

        resp = request.get_response(ztpserver.controller.Router())
        self.assertEqual(resp.status_code, 400)

    def test_node_exists(self, filestore):
        url = '/nodes'
        systemmac = random_string()
        body = json.dumps(dict(systemmac=systemmac))

        filestore.exists.return_value = True
        ztpserver.controller.create_filestore = filestore

        request = Request.blank(url, body=body, method='POST',
                                headers=ztp_headers())
        resp = request.get_response(ztpserver.controller.Router())

        location = 'http://localhost/nodes/%s' % systemmac

        self.assertTrue(filestore.return_value.write_file.called)
        self.assertEqual(resp.status_code, 409)
        self.assertEqual(resp.location, location)

    def test_post_config(self, filestore):
        url = '/nodes'
        systemmac = random_string()
        config = random_string()
        body = json.dumps(dict(systemmac=systemmac, config=config))

        filestore.return_value.exists.return_value = False
        ztpserver.controller.create_filestore = filestore

        request = Request.blank(url, body=body, method='POST',
                                headers=ztp_headers())
        resp = request.get_response(ztpserver.controller.Router())

        location = 'http://localhost/nodes/%s' % systemmac
        filename = '%s/startup-config' % systemmac

        filestore.return_value.add_folder.assert_called_with(systemmac)
        filestore.return_value.write_file.assert_called_with(filename, config)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.location, location)

    def test_post_node_success(self, filestore):
        node = create_node()

        definition_file = create_definition()
        definition_file.add_action()

        filestore.return_value.exists.return_value = False
        filestore.return_value.get_file.return_value.contents = \
            definition_file.as_yaml()

        ztpserver.controller.create_filestore = filestore

        ztpserver.neighbordb.topology.match_node = Mock(return_value=[Mock()])

        request = Request.blank('/nodes', body=node.as_json(), method='POST',
                                headers=ztp_headers())
        resp = request.get_response(ztpserver.controller.Router())

        location = 'http://localhost/nodes/%s' % node.systemmac
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.location, location)


@patch('ztpserver.controller.create_filestore')
class NodesControllerGetFsmIntegrationTests(unittest.TestCase):

    def setUp(self):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', False, 'default')

    def test_get_fsm_missing_node(self, filestore):
        filestore.return_value.get_file = \
            Mock(side_effect=ztpserver.repository.FileObjectNotFound)

        url = '/nodes/%s' % random_string()
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 400)

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_startup_config_wo_validation(self, *args):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', True, 'default')

        node = create_node()
        filestore = args[2]

        def exists(filepath):
            if filepath.endswith('startup-config'):
                return True
            return False
        filestore.return_value.exists = Mock(side_effect=exists)

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            raise ztpserver.repository.FileObjectNotFound

        filestore.return_value.get_file = Mock(side_effect=get_file)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertIsInstance(json.loads(resp.body), dict)

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_startup_config_w_validation_success(self, *args):
        node = create_node()
        filestore = args[2]

        def exists(filepath):
            if filepath.endswith('startup-config'):
                return True
            return False
        filestore.return_value.exists = Mock(side_effect=exists)

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('pattern'):
                return fileobj
            raise ztpserver.repository.FileObjectNotFound

        filestore.return_value.get_file = Mock(side_effect=get_file)

        cfg = {'return_value.match_node.return_value': True}
        args[1].configure_mock(**cfg)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertIsInstance(json.loads(resp.body), dict)

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_startup_config_w_validation_failure(self, *args):
        node = create_node()

        filestore = args[2]

        def exists(filepath):
            if filepath.endswith('startup-config'):
                return True
            return False
        filestore.return_value.exists = Mock(side_effect=exists)

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('pattern'):
                return fileobj
            raise ztpserver.repository.FileObjectNotFound
        filestore.return_value.get_file = Mock(side_effect=get_file)

        cfg = {'return_value.match_node.return_value': False}
        args[1].configure_mock(**cfg)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.content_type, 'text/html')
        self.assertEqual(resp.body, str())

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_definition_wo_validation(self, *args):
        ztpserver.config.runtime.set_value(\
            'disable_topology_validation', True, 'default')

        definitions_file = create_definition()
        definitions_file.add_action()

        node = create_node()
        filestore = args[2]

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('definition'):
                fileobj.contents = definitions_file.as_yaml()
                return fileobj
            raise ztpserver.repository.FileObjectNotFound
        filestore.return_value.get_file = Mock(side_effect=get_file)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertIsInstance(json.loads(resp.body), dict)

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_definition_w_validation_success(self, *args):
        node = create_node()

        definitions_file = create_definition()
        definitions_file.add_action()

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('definition'):
                fileobj.contents = definitions_file.as_yaml()
                return fileobj
            elif filepath.endswith('pattern'):
                return fileobj
            raise ztpserver.repository.FileObjectNotFound


        filestore = args[2]
        filestore.return_value.get_file = Mock(side_effect=get_file)

        cfg = {'return_value.match_node.return_value': True}
        args[1].configure_mock(**cfg)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')
        self.assertIsInstance(json.loads(resp.body), dict)

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_definition_w_validation_failure(self, *args):
        node = create_node()

        definitions_file = create_definition()
        definitions_file.add_action()

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('definition'):
                fileobj.contents = definitions_file.as_yaml()
                return fileobj
            raise ztpserver.repository.FileObjectNotFound

        filestore = args[2]
        filestore.return_value.get_file = Mock(side_effect=get_file)

        cfg = {'return_value.match_node.return_value': False}
        args[1].configure_mock(**cfg)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.content_type, 'text/html')
        self.assertEqual(resp.body, str())

    @patch('ztpserver.neighbordb.load_pattern')
    @patch('ztpserver.neighbordb.create_node')
    def test_get_definition_w_attributes_no_substitution(self, *args):
        node = create_node()

        g_attr_foo = random_string()
        attributes_file = create_attributes()
        attributes_file.add_attribute('variables', {'foo': g_attr_foo})

        l_attr_url = random_string()
        definitions_file = create_definition()
        definitions_file.add_attribute('foo', random_string())
        definitions_file.add_action(name='dummy action',
                                    attributes=dict(url=l_attr_url))

        filestore = args[2]

        def exists(filepath):
            if filepath.endswith('startup-config'):
                return False
            return True
        filestore.return_value.exists = Mock(side_effect=exists)

        def get_file(filepath):
            fileobj = Mock()
            if filepath.endswith('node'):
                fileobj.contents = node.as_json()
                return fileobj
            elif filepath.endswith('definition'):
                fileobj.contents = definitions_file.as_yaml()
                return fileobj
            elif filepath.endswith('attributes'):
                fileobj.contents = attributes_file.as_yaml()
                return fileobj
            elif filepath.endswith('pattern'):
                return fileobj
            raise ztpserver.repository.FileObjectNotFound
        filestore.return_value.get_file = Mock(side_effect=get_file)

        cfg = {'return_value.match_node.return_value': True}
        args[1].configure_mock(**cfg)

        url = '/nodes/%s' % node.systemmac
        request = Request.blank(url, method='GET')
        resp = request.get_response(ztpserver.controller.Router())

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/json')

        attrs = resp.json['actions'][0]['attributes']
        self.assertFalse('variables' in attrs)
        self.assertFalse('foo' in attrs)
        self.assertEqual(attrs['url'], l_attr_url)

if __name__ == '__main__':
    unittest.main()

