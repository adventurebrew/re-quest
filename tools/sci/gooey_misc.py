import sys

import gooey
import wx
from gooey.gui.components.widgets.dropdown import Dropdown


def force_english():
    from gooey.gui.containers.application import GooeyApplication
    orig_applyConfiguration = GooeyApplication.applyConfiguration

    def applyConfiguration(self):
        # don't take system language, but English
        # TODO: need to open an issue or PR (for __init__)
        self.locale = wx.Locale(wx.LANGUAGE_ENGLISH)

        # even with English, if the OS is RTL, the windows will be RTL - avoid this
        # based on https://github.com/chriskiehl/Gooey/pull/682/files
        self.SetLayoutDirection(wx.Layout_LeftToRight)

        orig_applyConfiguration(self)

    GooeyApplication.applyConfiguration = applyConfiguration


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


def run_gooey_only_if_no_args():
    # run GUI only if no arguments are supplied
    # taken from https://github.com/chriskiehl/Gooey/issues/449#issuecomment-534056010
    # hopefully, one day https://github.com/chriskiehl/Gooey/issues/296 will be fixed
    if len(sys.argv) >= 2:
        if not '--ignore-gooey' in sys.argv:
            sys.argv.append('--ignore-gooey')
