import sys
import warnings

import gooey
import wx
from gooey.gui.components.widgets.dropdown import Dropdown


def protected_func(func):
    def wrapper():
        try:
            func()
        except Exception as exception:
            warnings.warn(exception)

    return wrapper


@protected_func
def force_english():
    from gooey.gui.containers.application import GooeyApplication
    orig_applyConfiguration = GooeyApplication.applyConfiguration

    def applyConfiguration(self):
        # don't take system language, but English
        # TODO: need to open an issue or PR (for __init__), use 'language' attribute
        self.locale = wx.Locale(wx.LANGUAGE_ENGLISH)

        # even with English, if the OS is RTL, the windows will be RTL - avoid this
        # based on https://github.com/chriskiehl/Gooey/pull/682/files
        self.SetLayoutDirection(wx.Layout_LeftToRight)

        orig_applyConfiguration(self)

    GooeyApplication.applyConfiguration = applyConfiguration


@protected_func
def add_read_only_dropdown():
    # bypass until https://github.com/chriskiehl/Gooey/issues/828 will be fixed

    class ReadOnlyDropdown(Dropdown):
        def getWidget(self, parent, *args, **options):
            default = gooey.gui.lang.i18n._('select_option')
            return wx.ComboBox(
                parent=parent,
                id=-1,
                # str conversion allows using stringyfiable values in addition to pure strings
                value=str(default),
                choices=[str(default)] + [str(choice) for choice in self._meta['choices']],
                # Zvika - the following line is the only difference from regular DropDown
                style=wx.CB_READONLY)

    gooey.gui.components.widgets.ReadOnlyDropdown = ReadOnlyDropdown


gooey_enabled = True


@protected_func
def run_gooey_only_if_no_args():
    # run GUI only if no arguments are supplied
    # taken from https://github.com/chriskiehl/Gooey/issues/449#issuecomment-534056010
    # hopefully, one day https://github.com/chriskiehl/Gooey/issues/296 will be fixed
    if len(sys.argv) >= 2:
        global gooey_enabled
        if not '--ignore-gooey' in sys.argv:
            gooey_enabled = False
            sys.argv.append('--ignore-gooey')


@protected_func
def progress_bar_dont_display_remaining_time():
    # the remaining time isn't accurate; better to not display it
    # seems like it should be possible, but there is a bug in the official way
    from gooey.gui.util import time
    def estimate_time_remaining(progress, startTime):
        return None

    time.estimate_time_remaining = estimate_time_remaining


@protected_func
def args_replace_underscore_with_spaces():
    from gooey.python_bindings import argparse_to_json
    orig_action_to_json = argparse_to_json.action_to_json

    def action_to_json(action, widget, options):
        action.dest = action.dest.replace('_', ' ')
        return orig_action_to_json(action, widget, options)

    argparse_to_json.action_to_json = action_to_json


def find_gooey_object(name, somewhere):
    for child in somewhere.TopLevelParent.configs[0].Children:
        try:
            if child.info['id'] == name:
                return child
        except:
            pass
    return None


#### from down here, code specific for sounder


def my_widget_updates(cb):
    try:
        def default_disables(self):
            find_gooey_object('--play_device', self).widget.Enable(False)
            find_gooey_object('--port', self).widget.Enable(False)
            find_gooey_object('--save_file', self).widget.Enable(False)
            find_gooey_object('--save_wav_file', self).widget.Enable(False)

        # add my events binding
        def layoutComponent(self):
            self.Bind(wx.EVT_COMBOBOX, dropdown_cb)
            self.Bind(wx.EVT_CHECKBOX, checkbox_cb)
            self.Bind(wx.EVT_TEXT, text_cb)
            default_disables(self)
            orig_layoutComponent(self)

        from gooey.gui.containers.application import GooeyApplication
        orig_layoutComponent = GooeyApplication.layoutComponent
        GooeyApplication.layoutComponent = layoutComponent

        ####################################

        def update_play_options(self):
            input_files_obj = find_gooey_object('input_files', self)
            input_version_obj = find_gooey_object('--input_version', self)
            play_device_obj = find_gooey_object('--play_device', self)
            if input_files_obj and input_version_obj and play_device_obj:
                input_files = input_files_obj.widget.getValue()
                input_version = input_version_obj.widget.GetValue()
                options = cb(input_files, input_version)
                if options:
                    play_device_obj.setOptions(options)

        ####################################

        # combobox:
        def dropdown_cb(event):
            if event.EventObject.Parent.info['id'] == '--input_version':
                update_play_options(event.EventObject)
            elif event.EventObject.Parent.info['id'] == '--save':
                find_gooey_object('--save_file', event.EventObject).widget.Enable(bool(event.Selection))

        # file chooser
        def text_cb(event):
            try:
                if event.EventObject.Parent.Parent.Parent.info['id'] == 'input_files' and event.String:
                    update_play_options(event.EventObject)
            except AttributeError:
                pass

        # checkbox:
        def checkbox_cb(event):
            if event.EventObject.Parent.info['id'] == '--play':
                find_gooey_object('--play_device', event.EventObject).widget.Enable(bool(event.Selection))
                find_gooey_object('--port', event.EventObject).widget.Enable(bool(event.Selection))
            elif event.EventObject.Parent.info['id'] == '--save_wav':
                find_gooey_object('--save_wav_file', event.EventObject).widget.Enable(bool(event.Selection))


    except:
        pass
