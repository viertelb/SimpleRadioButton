A Windows system tray icon that has a play/stop mode for a small list of web radio stations (left click).

---

For installation you will need PyInstaller. This will create an executable file.

`python -m pip install pyinstaller`

`pyinstaller --onefile --noconsole --add-data="icons;icons" SimpleRadioButton.py`

---

All radio stations are non-commercial. They use only a minimum of hosting.

The app includes a list of websites for donation via paypal or patreon (right click). 

Quit option is found by right click. 

---

Known bugs

- First click after startup does not work properly.
- If menu is shown and is not closed by a click on the menu itself the next click will not do anything.
