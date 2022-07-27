import sys

import gooey
import wx
from gooey.gui.components.widgets.dropdown import Dropdown


# note: I've locally modified
# C:\Users\Zvika\anaconda3\envs\hebrew_adventure\Lib\site-packages\gooey\gui\containers\application.py
# added in init()
#       self.SetLayoutDirection(wx.Layout_LeftToRight)
# waiting for https://github.com/chriskiehl/Gooey/pull/682


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

# wx.Locale(wx.LANGUAGE_ENGLISH)
