# Released under the MIT License. See LICENSE for details.
#
"""Player-name prompt for the web (WebAssembly) build.

Web builds have no accounts, so the player's name is asked in-game:
on the first visit at startup, and again from the top-left 'Change
name' button. The name becomes the device name (what servers show for
players without an account) and a real player profile (so the lobby
uses it instead of a random name). The page stores it in localStorage
('@@name <name>' on stdout) and passes it back as BA_DEVICE_NAME on the
next visit.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, cast

import bauiv1 as bui
from bauiv1 import _commonassets

if TYPE_CHECKING:
    from typing import Callable

MAX_LEN = 16

_open: NameWindow | None = None


def clean(name: str) -> str:
    """Normalize a typed name (no control chars, single spaces, max 16)."""
    name = re.sub(r'[\x00-\x1f\x7f<>]', '', name)
    return re.sub(r'\s+', ' ', name).strip()[:MAX_LEN]


def current() -> str:
    """The player's name, or '' if none has been chosen yet."""
    return clean(os.environ.get('BA_DEVICE_NAME', ''))


def apply(name: str) -> None:
    """Make `name` the player's name for this session and future visits."""
    import _babase

    old = current()
    os.environ['BA_DEVICE_NAME'] = name
    _babase.set_device_name(name)

    profiles = bui.app.config.setdefault('Player Profiles', {})
    profile = profiles.pop(old, None) if old and old != name else None
    profiles[name] = profile or profiles.get(name) or default_profile()

    # Tell the page to remember it (localStorage).
    os.write(1, f'@@name {name}\n'.encode())


def default_profile() -> dict:
    """A plain Spaz profile for a newly named player."""
    return {
        'character': 'Spaz',
        'color': [0.13, 0.53, 1.0],
        'highlight': [1.0, 0.6, 0.1],
        'global': False,
        'icon': bui.SpecialChar.LOGO.value,
    }


def ask(on_done: Callable[[str], None] | None = None) -> None:
    """Show the name window (no-op if it is already open)."""
    global _open  # pylint: disable=global-statement
    if _open is not None and _open.alive():
        return
    _open = NameWindow(on_done=on_done)


def ask_at_startup() -> None:
    """On the first visit (no name yet), ask once the main menu is up."""
    if current():
        return

    def _try() -> None:
        if bui.app.ui_v1.has_main_window():
            ask()
        else:
            bui.apptimer(0.5, _try)

    bui.apptimer(1.0, _try)


class NameWindow:
    """Small overlay window with a text field for the player's name."""

    def __init__(self, on_done: Callable[[str], None] | None = None):
        ui = bui.app.ui_v1
        self._id_prefix = ui.new_id_prefix('webname')
        self._on_done = on_done
        first = not current()

        width = 460.0
        height = 220.0
        uiscale = ui.uiscale
        self._root_widget = bui.containerwidget(
            size=(width, height),
            transition='in_scale',
            toolbar_visibility='menu_minimal_no_back',
            parent=bui.get_special_widget('overlay_stack'),
            scale=(
                1.9
                if uiscale is bui.UIScale.SMALL
                else 1.5 if uiscale is bui.UIScale.MEDIUM else 1.0
            ),
            darken_behind=True,
        )
        bui.textwidget(
            parent=self._root_widget,
            position=(width * 0.5, height - 38),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='What\'s your name?' if first else 'Change your name',
            scale=1.1,
            color=(1.0, 0.75, 0.3),
            maxwidth=width * 0.9,
        )
        bui.textwidget(
            parent=self._root_widget,
            position=(width * 0.5, height - 68),
            size=(0, 0),
            h_align='center',
            v_align='center',
            text='Other players will see this in games.',
            scale=0.7,
            color=(0.7, 0.75, 0.85),
            maxwidth=width * 0.9,
        )
        self._text_field = bui.textwidget(
            parent=self._root_widget,
            id=f'{self._id_prefix}|name',
            editable=True,
            size=(width - 80, 44),
            position=(40, height - 130),
            text=current(),
            maxwidth=width - 100,
            max_chars=MAX_LEN,
            autoselect=True,
            v_align='center',
            description='Your name',
            on_submit_call=self._submit,
        )
        okbtn = bui.buttonwidget(
            parent=self._root_widget,
            id=f'{self._id_prefix}|ok',
            autoselect=True,
            position=(width - 190, 20),
            size=(160, 52),
            label='Play' if first else _commonassets.strings.actions.ok,
            on_activate_call=self._submit,
        )
        if first:
            # Naming is required the first time: no cancel.
            bui.containerwidget(
                edit=self._root_widget,
                start_button=okbtn,
                selected_child=self._text_field,
            )
        else:
            cbtn = bui.buttonwidget(
                parent=self._root_widget,
                id=f'{self._id_prefix}|cancel',
                autoselect=True,
                position=(30, 20),
                size=(160, 52),
                label=_commonassets.strings.actions.cancel,
                on_activate_call=self._close,
            )
            bui.containerwidget(
                edit=self._root_widget,
                cancel_button=cbtn,
                start_button=okbtn,
                selected_child=self._text_field,
            )

    def alive(self) -> bool:
        """Whether the window is still on screen."""
        return bool(self._root_widget)

    def _submit(self) -> None:
        if not self._root_widget:
            return
        name = clean(cast(str, bui.textwidget(query=self._text_field)))
        if not name:
            bui.screenmessage('Type a name first', color=(1, 0.5, 0.2))
            bui.getsound('error').play()
            return
        apply(name)
        bui.screenmessage(f'Hi {name}!', color=(0.4, 1, 0.4))
        self._close()
        if self._on_done is not None:
            self._on_done(name)

    def _close(self) -> None:
        if self._root_widget:
            bui.containerwidget(edit=self._root_widget, transition='out_scale')
