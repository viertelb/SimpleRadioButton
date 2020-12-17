#!/usr/bin/env python
# Copyright 2020 Benjamin Viertel
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import sys
import win32ui
import vlc as vlcimp
import os
import win32api
import win32con
import win32gui_struct
import threading
import webbrowser

try:
    import winxpgui as win32gui
except ImportError:
    import win32gui

class SysTrayIcon(object):
    QUIT = 'QUIT'
    STOP = 'STOP'
    SPECIAL_ACTIONS = [STOP, QUIT]
    FIRST_ID = 1023
    def __init__(self,
                 icon,
                 hover_text,
                 menu_options,
                 menu_options2,
                 on_quit=None,
                 default_menu_index=None,
                 window_class_name=None,):

        self.button_doubleclicked = False
        self.playing = None
        self.playingID = ''
        self.toggle = False
        self.vlc = vlcimp.Instance()
        self.player = self.vlc.media_player_new()
        self.icon = icon
        self.hover_text = hover_text
        self.on_quit = on_quit
        self.menu = None

        self.media_list = []
        self.icon_list = []
        opt_default = ''
        menu_options                = menu_options + (('Stop', None, self.STOP, opt_default),)
        menu_options2               = menu_options2 + (('Quit', None, self.QUIT, opt_default),)

        self._next_action_id        = self.FIRST_ID
        self.menu_actions_by_id     = set()
        self.menu_options           = self._add_ids_to_menu_options(list(menu_options))

        self.menu_options2          = self._add_ids_to_menu_options(list(menu_options2))
        self.menu_actions_by_id     = dict(self.menu_actions_by_id)
        del self._next_action_id

        self.default_menu_index = (default_menu_index or 0)
        self.window_class_name = window_class_name or "SystemTrayRadio"

        message_map = {win32gui.RegisterWindowMessage("TaskbarCreated"):    self.restart,
                       win32con.WM_DESTROY:                                 self.destroy,
                       win32con.WM_COMMAND:                                 self.command,
                       win32con.WM_USER+20:                                 self.notify,}

        hinst = win32gui.GetModuleHandle(None)
        window_class                = win32gui.WNDCLASS()
        window_class.hInstance      = hinst
        window_class.lpszClassName  = self.window_class_name
        window_class.style          = win32con.CS_VREDRAW | win32con.CS_HREDRAW;
        window_class.hCursor        = win32gui.LoadCursor(0, win32con.IDC_ARROW)
        window_class.hbrBackground  = win32con.COLOR_WINDOW
        window_class.lpfnWndProc    = message_map
        classAtom                   = win32gui.RegisterClass(window_class)
        style                       = win32con.WS_OVERLAPPED | win32con.WS_SYSMENU
        self.hwnd = win32gui.CreateWindow(classAtom,
                                          self.window_class_name,
                                          style,
                                          0,
                                          0,
                                          win32con.CW_USEDEFAULT,
                                          win32con.CW_USEDEFAULT,
                                          0,
                                          0,
                                          hinst,
                                          None)
        win32gui.UpdateWindow(self.hwnd)
        self.notify_id = None
        self.refresh_icon()
        win32gui.PumpMessages()

    def _add_ids_to_menu_options(self, menu_options):
        result = []
        for menu_option in menu_options:
            option_text, option_icon, option_action, option_medium = menu_option
            if callable(option_action) or option_action in self.SPECIAL_ACTIONS:
                self.menu_actions_by_id.add((self._next_action_id, option_action))          # callable action
                result.append(menu_option + (self._next_action_id,))                        # menu
                self.make_media_list(self._next_action_id, option_medium, option_icon)      # make URLs & icons
            elif non_string_iterable(option_action):
                result.append((option_text,
                               option_icon,
                               self._add_ids_to_menu_options(option_action),
                               self._next_action_id))
            else:
                print('Unknown item', option_text, option_icon, option_action)
            self._next_action_id += 1

        return result

    def make_media_list(self, id, medium, icon):
        self.media_list.append((id, medium))
        self.icon_list.append((id,icon))

    def refresh_icon(self):
        hinst = win32gui.GetModuleHandle(None)
        if os.path.isfile(self.icon):
            icon_flags = win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE
            hicon = win32gui.LoadImage(hinst,
                                       self.icon,
                                       win32con.IMAGE_ICON,
                                       0,
                                       0,
                                       icon_flags)
        else:
            print("Can't find icon file - using default.")
            hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)

        if self.notify_id: message = win32gui.NIM_MODIFY
        else: message = win32gui.NIM_ADD
        self.notify_id = (self.hwnd,
                          0,
                          win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP,
                          win32con.WM_USER+20,
                          hicon,
                          self.hover_text)
        win32gui.Shell_NotifyIcon(message, self.notify_id)

    def restart(self, hwnd, msg, wparam, lparam):
        self.refresh_icon()

    def destroy(self, hwnd, msg, wparam, lparam):
        if self.on_quit: self.on_quit(self)
        nid = (self.hwnd, 0)
        win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, nid)
        win32gui.PostQuitMessage(0)

    def notify(self, hwnd, msg, wparam, lparam):
        if lparam==win32con.WM_LBUTTONUP and self.toggle == False:
            self.show_menu()
            lparam = 512
            self.toggle = True

        if lparam==win32con.WM_RBUTTONUP and self.toggle == False:
            self.show_menu2()
            lparam = 512
            self.toggle = True
        if (lparam==win32con.WM_LBUTTONUP or lparam==win32con.WM_RBUTTONUP ) and self.toggle == True:
            self.toggle = False
        return True

    def show_menu(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options)
        # win32gui.SetMenuDefaultItem(self.menu, 1000, 0)
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu,
                                win32con.TPM_LEFTALIGN,
                                pos[0],
                                pos[1],
                                0,
                                self.hwnd,
                                None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)


    def show_menu2(self):
        menu = win32gui.CreatePopupMenu()
        self.create_menu(menu, self.menu_options2)
        pos = win32gui.GetCursorPos()
        win32gui.SetForegroundWindow(self.hwnd)
        win32gui.TrackPopupMenu(menu,
                                win32con.TPM_LEFTALIGN,
                                pos[0],
                                pos[1],
                                0,
                                self.hwnd,
                                None)
        win32gui.PostMessage(self.hwnd, win32con.WM_NULL, 0, 0)

    def create_menu(self, menu, menu_options):
        for option_text, option_icon, option_action, option_medium, option_id in menu_options[::-1]:
            if option_icon:
                option_icon = self.prep_menu_icon(option_icon)
            if option_id in self.menu_actions_by_id:
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                wID=option_id)
                win32gui.InsertMenuItem(menu, 0, 1, item)
            else:
                submenu = win32gui.CreatePopupMenu()                                    #
                self.create_menu(submenu, option_action)
                item, extras = win32gui_struct.PackMENUITEMINFO(text=option_text,
                                                                hbmpItem=option_icon,
                                                                hSubMenu=submenu)
                win32gui.InsertMenuItem(menu, 0, 1, item)

    def prep_menu_icon(self, icon):
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXSMICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYSMICON)
        hicon = win32gui.LoadImage(0, icon, win32con.IMAGE_ICON, ico_x, ico_y, win32con.LR_LOADFROMFILE)
        hdcBitmap = win32gui.CreateCompatibleDC(0)
        hdcScreen = win32gui.GetDC(0)
        hbm = win32gui.CreateCompatibleBitmap(hdcScreen, ico_x, ico_y)
        hbmOld = win32gui.SelectObject(hdcBitmap, hbm)
        brush = win32gui.GetSysColorBrush(win32con.COLOR_MENU)
        win32gui.FillRect(hdcBitmap, (0, 0, 16, 16), brush)
        win32gui.DrawIconEx(hdcBitmap, 0, 0, hicon, ico_x, ico_y, 0, 0, win32con.DI_NORMAL)
        win32gui.SelectObject(hdcBitmap, hbmOld)
        win32gui.DeleteDC(hdcBitmap)
        return hbm

    def command(self, hwnd, msg, wparam, lparam):
        id = win32gui.LOWORD(wparam)
        self.execute_menu_option(id)
        self.toggle = False

    def execute_menu_option(self, id):
        menu_action = self.menu_actions_by_id[id]
        self.media_list = dict(self.media_list)
        self.icon_list = dict(self.icon_list)
        if menu_action == self.STOP:
            self.icon = list_icons[0]
            self.refresh_icon()
            self.player.stop()
        elif menu_action == self.QUIT:
            win32gui.DestroyWindow(self.hwnd)
        else:
            menu_action(self, id)

def non_string_iterable(obj):
    try:
        iter(obj)
    except TypeError:
        return False
    else:
        return not isinstance(obj, str)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        print("Exception - no sys._MEIPASS")
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

if __name__ == '__main__':

    if getattr(sys, 'frozen', True) and hasattr(sys, '_MEIPASS'):
        print('Running in a PyInstaller bundle')
        print("sys._MEIPASS: "+ str(sys._MEIPASS))
    else:
        print('Running in a normal Python process')

    def prepare_icons():
        path = resource_path("icons")
        playDHR = path + '\\DHRplay.ico'
        stopDHR = path + '\\DHRstop.ico'
        playGROOVE = path + '\\GROOVEplay.ico'
        stopGROOVE = path + '\\GROOVEstop.ico'
        playKBAQ = path + '\\KBAQplay.ico'
        stopKBAQ = path + '\\KBAQstop.ico'
        playKJAZZ = path + '\\KJAZZplay.ico'
        stopKJAZZ = path + '\\KJAZZstop.ico'
        list_icons = [
            playDHR,
            stopDHR,
            playGROOVE,
            stopGROOVE,
            playKBAQ,
            stopKBAQ,
            playKJAZZ,
            stopKJAZZ
            ]
        return list_icons

    list_icons = prepare_icons()
    hover_text = "No commercials. No news."

    def play(sysTrayIcon, id):
        sysTrayIcon.playingID = id
        sysTrayIcon.media = sysTrayIcon.vlc.media_new(sysTrayIcon.media_list[id])
        sysTrayIcon.icon = sysTrayIcon.icon_list[id]
        sysTrayIcon.player.set_media(sysTrayIcon.media)
        def playth():
            sysTrayIcon.player.play()
        t1 = threading.Thread(target=playth)
        t1.start()
        t1.join()
        sysTrayIcon.refresh_icon()
        sysTrayIcon.playing = True

    def brauser(sysTrayIcon, id):
        sysTrayIcon.url = sysTrayIcon.media_list[id]
        webbrowser.open(sysTrayIcon.url)


    url1 = 'https://www.deephouse-radio.com'
    url2 = 'https://jazzgroove.org'
    url3 = 'https://kbaq.org'
    url4 = 'www.patreon.com/deephouseradio'
    url5 = 'https://www.kkjz.org/support/'
    url99 = 'https://www.patreon.com/bomben'

    media1 = 'https://deephouseradio.radioca.st/;'
    media2 = 'http://west-mp3-128.streamthejazzgroove.com/stream/1/'
    media3 = 'https://kbaq.streamguys1.com/kbaq_mp3_128'
    media4 = 'http://1.ice1.firststreaming.com/kkjz_fm.mp3'


    menu_options = (('Deephouse Radio ', list_icons[1], play, media1),
                    ('The Jazz Groove', list_icons[2], play, media2),
                    ('KBAQ', list_icons[4], play, media3),
                    ('KJAZZ', list_icons[6], play, media4)
                   )

    menu_options2 = (('visit deephouse-radio.com', None, brauser, url1),
                     ('visit jazzgroove.org', None, brauser, url2),
                     ('visit kbaq.org', None, brauser, url3),
                     ('patreon DHR', None, brauser, url4),
                     ('visit kjazz.org', None, brauser, url5),
                     ('patreon App', None, brauser, url99),
                     )

    def bye(sysTrayIcon): print('Bye, then.')

    SysTrayIcon(list_icons[0],
                hover_text,
                menu_options,
                menu_options2,
                on_quit=bye,
                default_menu_index=1)
