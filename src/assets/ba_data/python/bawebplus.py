# Released under the MIT License. See LICENSE for details.
#
"""Offline stand-in for the closed-source native ``_baplus`` module.

Web (emscripten) builds can't link the plus feature-set (it ships only
as precompiled native libs), and self-hosted servers built with the
NO_PLUS cmake option leave it out. Much game code assumes ``app.plus``
exists, so instead of patching every call site we provide this
pure-Python ``_baplus`` (registered in sys.modules by bawebshims on web,
by baenv on native). The open-source ``baplus`` package then runs on top
of it unchanged.

Everything here behaves like a permanently offline client with nobody
signed in: no accounts, no cloud, no purchases, no ads. Local play and
joining servers by address don't need any of that.
"""


import os
import sys
import concurrent.futures
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable

    from baplus import PlusAppSubsystem

_OFFLINE_MSG = 'Cloud functionality is not available in this build.'

# Lets babase tell this stand-in apart from the real native _baplus.
IS_OFFLINE_STANDIN = True

# ---------------------------------------------------------------------------
# Native _baplus function surface (see baplus/_appsubsystem.py, _ads.py).
# ---------------------------------------------------------------------------


def web_stage(name: str) -> None:
    """Tell the HTML shell's loading screen which startup stage we're in.

    Written straight to fd 1 (Emscripten routes it to Module.print, where
    the shell picks up '@@stage <name>' lines) so it doesn't depend on
    the engine's stdout redirection or log levels.
    """
    if sys.platform == 'emscripten':
        os.write(1, f'@@stage {name}\n'.encode())


def on_app_loading() -> None:
    """Called by PlusAppSubsystem.on_app_loading()."""
    import _babase

    web_stage('loading')

    # Native builds always end up with this config key (empty when there
    # are no saved profiles); the lobby reads it unconditionally when a
    # player joins, so make sure it exists.
    profiles = _babase.app.config.setdefault('Player Profiles', {})

    # Web: the player's name (asked in-game, remembered by the page and
    # passed back as BA_DEVICE_NAME) becomes a real player profile. With
    # no account the lobby otherwise only has '_random' and hands out
    # random names ('Leonidas'); it gives the first local player the
    # first real profile, and joining a server sends this profile along.
    # No name yet (first visit): ask once the main menu is up.
    if sys.platform == 'emscripten':
        import babase

        def _name_setup() -> None:
            from bauiv1lib import webname

            name = webname.current()
            if name:
                profiles.setdefault(name, webname.default_profile())
            else:
                webname.ask_at_startup()

        babase.pushcall(_name_setup)


def set_v1_account_client_active(active: bool) -> None:
    """No v1 account client in web builds."""
    del active


def add_v1_account_transaction(transaction: dict, callback: Any) -> None:
    """Apply what makes sense locally; everything else goes nowhere.

    Player profiles are kept in the local config (the native game keeps
    them on the v1 account), so the profile editor works on the web.
    """
    del callback
    import _babase

    kind = transaction.get('type')
    profiles = _babase.app.config.setdefault('Player Profiles', {})
    if kind == 'ADD_PLAYER_PROFILE':
        profiles[transaction['name']] = dict(transaction['profile'])
    elif kind == 'REMOVE_PLAYER_PROFILE':
        profiles.pop(transaction['name'], None)
    elif kind == 'SET_PLAYER_PROFILE_GLOBAL':
        pass  # No global (account-wide) profiles offline.


def have_outstanding_v1_account_transactions() -> bool:
    """Never any outstanding transactions."""
    return False


def run_v1_account_transactions() -> None:
    """Save locally applied changes (profiles)."""
    import _babase

    _babase.app.config.commit()


def game_service_has_leaderboard(game: str, config: str) -> bool:
    """No game services."""
    del game, config
    return False


def get_legacy_master_server_address() -> str:
    """No master server."""
    return ''


def get_master_server_address() -> str:
    """No master server."""
    return ''


def get_bootstrap_server_addresses() -> list[str]:
    """No bootstrap servers."""
    return []


def get_bootstrap_server_address() -> str | None:
    """No bootstrap server."""
    return None


def get_classic_news_show() -> str:
    """No news."""
    return ''


def get_price(item: str) -> str | None:
    """Nothing is for sale."""
    del item
    return None


def get_v1_account_display_string(full: bool = True) -> str:
    """Shown e.g. as the main-menu host name."""
    del full
    return 'Web Player'


def get_v1_account_misc_read_val(name: str, default_value: Any) -> Any:
    """No account values; always the default."""
    del name
    return default_value


def get_v1_account_misc_read_val_2(name: str, default_value: Any) -> Any:
    """No account values; always the default."""
    del name
    return default_value


def get_v1_account_misc_val(name: str, default_value: Any) -> Any:
    """No account values; always the default."""
    del name
    return default_value


def get_v1_account_name() -> str:
    """No account."""
    return ''


def get_v1_account_public_login_id() -> str | None:
    """No account."""
    return None


def get_v1_account_state() -> str:
    """Never signed in (callers compare against 'signed_in')."""
    return 'signed_out'


def get_v1_account_state_num() -> int:
    """State counter; never changes offline."""
    return 0


def get_v1_account_type() -> str:
    """No account type."""
    return 'Local'


def get_v2_fleet() -> str:
    """No fleet."""
    return 'none'


def in_game_purchase(item: str, price: int) -> None:
    """No purchases."""
    del item, price


def purchase(item: str) -> None:
    """No purchases."""
    del item


def restore_purchases() -> None:
    """No purchases."""


def supports_purchases() -> bool:
    """No purchases."""
    return False


def is_blessed() -> bool:
    """Web builds are never official 'blessed' builds."""
    return False


def get_blessing_state() -> str:
    """See PlusAppSubsystem.blessed_state()."""
    return 'unblessed'


def power_ranking_query(callback: Callable, season: Any = None) -> None:
    """No rankings offline; report 'no data'."""
    del season
    _push(callback, None)


def tournament_query(callback: Callable, args: dict) -> None:
    """No tournaments offline; report 'no data'."""
    del args
    _push(callback, None)


def report_achievement(achievement: str, pass_to_account: bool = True) -> None:
    """Achievements aren't tracked offline."""
    del achievement, pass_to_account


def reset_achievements() -> None:
    """Achievements aren't tracked offline."""


def submit_score(*args: Any, **kwargs: Any) -> None:
    """Scores go nowhere offline; tell the caller there's no result."""
    # Positional as passed by PlusAppSubsystem.submit_score():
    # (game, config, name, score, callback, order, ...).
    callback = kwargs.get('callback')
    if callback is None and len(args) >= 5 and callable(args[4]):
        callback = args[4]
    if callback is not None:
        _push(callback, None)


def sign_in_v1(account_type: str) -> None:
    """No v1 sign-in in web builds."""
    del account_type


def sign_out_v1(v2_embedded: bool = False) -> None:
    """No v1 sign-in in web builds."""
    del v2_embedded


def show_game_service_ui(
    show: str = 'general', game: str | None = None, game_version: Any = None
) -> None:
    """No game services."""
    del show, game, game_version


def can_show_ad() -> bool:
    """No ads."""
    return False


def has_video_ads() -> bool:
    """No ads."""
    return False


def have_incentivized_ad() -> bool:
    """No ads."""
    return False


def show_ad(purpose: str, on_completion_call: Callable | None = None) -> None:
    """No ads; complete immediately."""
    del purpose
    if on_completion_call is not None:
        _push(on_completion_call)


def show_ad_2(
    purpose: str, on_completion_call: Callable[[bool], None] | None = None
) -> None:
    """No ads; complete immediately, reporting nothing was shown."""
    del purpose
    if on_completion_call is not None:
        _push(on_completion_call, False)


def _push(call: Callable, *args: Any) -> None:
    """Run a callback on the logic thread later (never synchronously)."""
    import _babase

    _babase.pushcall(
        lambda: call(*args), from_other_thread=not _babase.in_logic_thread()
    )


# ---------------------------------------------------------------------------
# Attaching offline accounts/cloud to the PlusAppSubsystem.
# ---------------------------------------------------------------------------


def attach(plus: PlusAppSubsystem) -> None:
    """Give a PlusAppSubsystem the parts native plus normally provides.

    Called while app.plus is still being constructed. The cloud can be
    made right away, but AccountV2Subsystem's constructor reads
    app.plus (to register for connectivity callbacks), which would be a
    subsystem dependency loop now -- so accounts get built lazily on
    first access, by which point app.plus exists.
    """
    plus.cloud = _make_cloud()

    base_cls = type(plus)

    class WebPlusAppSubsystem(base_cls):  # type: ignore[valid-type,misc]
        """PlusAppSubsystem with lazily-created offline accounts."""

        _web_accounts: Any = None

        @property
        def accounts(self) -> Any:  # type: ignore[override]
            """Offline account subsystem (created on first use)."""
            if self._web_accounts is None:
                self._web_accounts = _make_accounts()
            return self._web_accounts

        def on_app_running(self) -> None:
            super().on_app_running()
            web_stage('running')

    WebPlusAppSubsystem.__name__ = base_cls.__name__
    WebPlusAppSubsystem.__qualname__ = base_cls.__qualname__
    plus.__class__ = WebPlusAppSubsystem


def _make_cloud() -> Any:
    from efro.error import CommunicationError
    from babase._cloud import CloudSubscription
    from baplus._cloud import CloudSubsystem

    class OfflineCloudSubsystem(CloudSubsystem):
        """A cloud that is never connected."""

        def is_connected(self) -> bool:
            return False

        def debug_drop_transport_session(
            self,
            on_done: Callable[[], None],
            *,
            block_reconnect: bool = False,
        ) -> None:
            del block_reconnect
            _push(on_done)

        def send_message_cb(  # type: ignore[override]
            self, msg: Any, on_response: Callable[[Any], None]
        ) -> None:
            del msg
            _push(on_response, CommunicationError(_OFFLINE_MSG))

        def send_message(self, msg: Any) -> Any:  # type: ignore[override]
            del msg
            raise CommunicationError(_OFFLINE_MSG)

        def send_message_future(  # type: ignore[override]
            self, msg: Any
        ) -> concurrent.futures.Future[Any]:
            del msg
            fut: concurrent.futures.Future[Any] = concurrent.futures.Future()
            fut.set_exception(CommunicationError(_OFFLINE_MSG))
            return fut

        async def send_message_async(  # type: ignore[override]
            self, msg: Any
        ) -> Any:
            del msg
            raise CommunicationError(_OFFLINE_MSG)

        def subscribe_test(self, updatecall: Any) -> CloudSubscription:
            del updatecall
            return CloudSubscription(-1)

        def subscribe_classic_account_data(
            self, updatecall: Any
        ) -> CloudSubscription:
            del updatecall
            return CloudSubscription(-1)

        def unsubscribe(self, subscription_id: int) -> None:
            del subscription_id

    return OfflineCloudSubsystem()


def _make_accounts() -> Any:
    from babase._accountv2 import AccountV2Subsystem

    class OfflineAccountV2Subsystem(AccountV2Subsystem):
        """Accounts with nobody ever signed in."""

        def have_primary_credentials(self) -> bool:
            return False

        def do_get_primary(self) -> Any:
            return None

        def set_primary_credentials(self, credentials: str | None) -> None:
            del credentials

        def on_app_loading(self) -> None:
            super().on_app_loading()
            # Native plus reports this once it knows there's no stored
            # account; the app waits for it (or a sign-in) before
            # leaving its launch fade. Offline, there never is one.
            _push(self.on_no_initial_primary_account)

    return OfflineAccountV2Subsystem()
