'''GTK Apport user interface tests.'''

# Copyright (C) 2012 Canonical Ltd.
# Author: Evan Dandrea <evan.dandrea@canonical.com>
# 
# This program is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation; either version 2 of the License, or (at your
# option) any later version.  See http://www.gnu.org/copyleft/gpl.html for
# the full text of the license.

import unittest
import tempfile
import sys
import os
import imp
import apport
from gi.repository import GLib, Gtk
from apport import unicode_gettext as _
from mock import patch

if os.environ.get('APPORT_TEST_LOCAL'):
    apport_gtk_path = 'gtk/apport-gtk'
else:
    apport_gtk_path = os.path.join(os.environ.get('APPORT_DATA_DIR', '/usr/share/apport'), 'apport-gtk')
GTKUserInterface = imp.load_source('', apport_gtk_path).GTKUserInterface

class T(unittest.TestCase):
    def setUp(self):
        self.report = apport.Report()
        saved = sys.argv[0]
        # Work around GTKUserInterface using basename to find the GtkBuilder UI
        # file.
        sys.argv[0] = apport_gtk_path
        self.app = GTKUserInterface()
        sys.argv[0] = saved
        self.app.report = self.report
        self.app.report_file = '/var/crash/fake.crash'

    def test_close_button(self):
        '''Clicking the close button on the window does not report the crash.'''

        self.app.w('send_error_report').set_active(True)
        def c(*args):
            self.app.w('dialog_crash_new').destroy()
        GLib.idle_add(c)
        result = self.app.ui_present_report_details(True)
        self.assertFalse(result['report'])

    def test_kernel_crash_layout(self):
        '''
        +-----------------------------------------------------------------+
        | [ ubuntu ] Ubuntu has restarted after experiencing an internal  |
        |            error.                                               |
        |                                                                 |
        |            [x] Send an error report to help fix this problem.   |
        |                                                                 |
        | [ Show Details ]                                   [ Continue ] |
        +-----------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'KernelCrash'
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Ubuntu has restarted after experiencing an internal error.'))
        send_error_report = self.app.w('send_error_report')
        self.assertTrue(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertTrue(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Continue'))
        self.assertFalse(self.app.w('closed_button').get_property('visible'))
        self.assertFalse(self.app.w('subtitle_label').get_property('visible'))

    def test_package_crash_layout(self):
        '''
        +-----------------------------------------------------------------+
        | [ error  ] Sorry, a problem occurred while installing software. |
        |            Package: apport 1.2.3~0ubuntu1                       |
        |                                                                 |
        |            [x] Send an error report to help fix this problem.   |
        |                                                                 |
        | [ Show Details ]                                   [ Continue ] |
        +-----------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'Package'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Sorry, a problem occurred while installing software.'))
        send_error_report = self.app.w('send_error_report')
        self.assertTrue(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertTrue(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Continue'))
        self.assertFalse(self.app.w('closed_button').get_property('visible'))
        self.assertTrue(self.app.w('subtitle_label').get_property('visible'))
        self.assertEqual(self.app.w('subtitle_label').get_text(),
                         _('Package: apport 1.2.3~0ubuntu1'))

    def test_regular_crash_layout(self):
        '''
        +-----------------------------------------------------------------+
        | [ apport ] The application Apport has closed unexpectedly.      |
        |                                                                 |
        |            [x] Send an error report to help fix this problem.   |
        |                                                                 |
        | [ Show Details ]                 [ Leave Closed ]  [ Relaunch ] |
        +-----------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'Crash'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'
        with tempfile.NamedTemporaryFile() as fp:
            fp.write('''[Desktop Entry]
Version=1.0
Name=Apport
Type=Application''')
            fp.flush()
            self.report['DesktopFile'] = fp.name
            GLib.idle_add(Gtk.main_quit)
            self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('The application Apport has closed unexpectedly.'))
        send_error_report = self.app.w('send_error_report')
        self.assertTrue(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertTrue(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Relaunch'))
        self.assertTrue(self.app.w('closed_button').get_property('visible'))
        self.assertFalse(self.app.w('subtitle_label').get_property('visible'))

    def test_system_crash_layout(self):
        '''
        +-----------------------------------------------------------------+
        | [ ubuntu ] Sorry, Ubuntu has experienced an internal error.     |
        |            If you notice further problems, try restarting the   |
        |            computer                                             |
        |                                                                 |
        |            [x] Send an error report to help fix this problem.   |
        |                                                                 |
        | [ Show Details ]                                   [ Continue ] |
        +-----------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'Crash'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Sorry, Ubuntu has experienced an internal error.'))
        self.assertEqual(self.app.w('subtitle_label').get_text(),
            _('If you notice further problems, try restarting the computer.'))
        self.assertTrue(self.app.w('subtitle_label').get_property('visible'))
        send_error_report = self.app.w('send_error_report')
        self.assertTrue(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertTrue(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Continue'))
        self.assertFalse(self.app.w('closed_button').get_property('visible'))

    def test_system_crash_from_console_layout(self):
        '''
        +-------------------------------------------------------------------+
        | [ ubuntu ] Sorry, the application apport has closed unexpectedly. |
        |            If you notice further problems, try restarting the     |
        |            computer                                               |
        |                                                                   |
        |            [x] Send an error report to help fix this problem.     |
        |                                                                   |
        | [ Show Details ]                                     [ Continue ] |
        +-------------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'Crash'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'
        self.report['ProcEnviron'] = ('LANGUAGE=en_GB:en\n'
                                      'SHELL=/bin/sh\n'
                                      'TERM=xterm')
        self.report['ExecutablePath'] = '/usr/bin/apport'
        # This will be set by apport/ui.py in load_report()
        self.app.cur_package = 'apport'
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Sorry, the application apport has closed unexpectedly.'))
        self.assertEqual(self.app.w('subtitle_label').get_text(),
            _('If you notice further problems, try restarting the computer.'))
        self.assertTrue(self.app.w('subtitle_label').get_property('visible'))
        send_error_report = self.app.w('send_error_report')
        self.assertTrue(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertTrue(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Continue'))
        self.assertFalse(self.app.w('closed_button').get_property('visible'))

        del self.report['ExecutablePath']
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Sorry, apport has closed unexpectedly.'))

    @patch.object(GTKUserInterface, 'can_examine_locally')
    def test_examine_button(self, *args):
        '''
        +---------------------------------------------------------------------+
        | [ apport ] The application Apport has closed unexpectedly.          |
        |                                                                     |
        |            [x] Send an error report to help fix this problem.       |
        |                                                                     |
        | [ Show Details ] [ Examine locally ]  [ Leave Closed ] [ Relaunch ] |
        +---------------------------------------------------------------------+
        '''
        self.report['ProblemType'] = 'Crash'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'

        GLib.idle_add(Gtk.main_quit)
        self.app.can_examine_locally.return_value = False
        self.app.ui_present_report_details(True)
        self.assertFalse(self.app.w('examine').get_property('visible'))

        GLib.idle_add(self.app.w('examine').clicked)
        self.app.can_examine_locally.return_value = True
        result = self.app.ui_present_report_details(True)
        self.assertTrue(self.app.w('examine').get_property('visible'))
        self.assertTrue(result['examine'])

    def test_apport_bug_package(self):
        '''
        +-------------------------------------------------------------------+
        | [ error  ] Send problem report to the developers?                 |
        |                                                                   |
        |            +----------------------------------------------------+ |
        |            | |> ApportVersion                                   | |
        |            | ...                                                | |
        |            +----------------------------------------------------+ |
        |                                                                   |
        | [ Cancel ]                                               [ Send ] |
        +-------------------------------------------------------------------+
        '''
        self.app.report_file = None
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)
        self.assertEqual(self.app.w('title_label').get_text(),
            _('Send problem report to the developers?'))
        self.assertFalse(self.app.w('subtitle_label').get_property('visible'))
        send_error_report = self.app.w('send_error_report')
        self.assertFalse(send_error_report.get_property('visible'))
        self.assertTrue(send_error_report.get_active())
        self.assertFalse(self.app.w('show_details').get_property('visible'))
        self.assertTrue(self.app.w('continue_button').get_property('visible'))
        self.assertEqual(self.app.w('continue_button').get_label(), 
                         _('Send'))
        self.assertFalse(self.app.w('closed_button').get_property('visible'))
        self.assertTrue(self.app.w('cancel_button').get_property('visible'))
        self.assertTrue(self.app.w('details_scrolledwindow').get_property('visible'))

    def test_administrator_disabled_reporting(self):
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(False)
        send_error_report = self.app.w('send_error_report')
        self.assertFalse(send_error_report.get_property('visible'))
        self.assertFalse(send_error_report.get_active())

    @patch.object(GTKUserInterface, 'get_desktop_entry')
    def test_missing_icon(self, *args):
        # LP: 937354
        self.report['ProblemType'] = 'Crash'
        self.report['Package'] = 'apport 1.2.3~0ubuntu1'
        self.app.get_desktop_entry.return_value.getIcon.return_value = 'nonexistent'
        self.app.get_desktop_entry.return_value.getName.return_value = 'apport'
        GLib.idle_add(Gtk.main_quit)
        self.app.ui_present_report_details(True)

unittest.main()