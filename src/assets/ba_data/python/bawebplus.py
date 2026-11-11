# Released under the MIT License. See LICENSE for details.
#
"""Offline stand-in for the closed-source native ``_baplus`` module.

Web (emscripten) builds can't link the plus feature-set (it ships only
as precompiled native libs). Much game code assumes ``app.plus`` exists,
so instead of patching every call site we provide this pure-Python
``_baplus`` (registered in sys.modules by bawebshims). The open-source
``baplus`` package then runs on top of it unchanged.

Everything here behaves like a permanently offline client with nobody
signed in: no accounts, no cloud, no purchases, no ads. Local play and
joining servers by address don't need any of that.
"""

from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Callable

    from baplus import PlusAppSubsystem

_OFFLINE_MSG = 'Cloud functionality is not available in web builds.'

# ---------------------------------------------------------------------------
# Native _baplus function surface (see baplus/_appsubsystem.py, _ads.py).
# ---------------------------------------------------------------------------


def on_app_loading() -> None:
    """Called by PlusAppSubsystem.on_app_loading()."""


def set_v1_account_client_active(active: bool) -> None:
    """No v1 account client in web builds."""
    del active


def add_v1_account_transaction(transaction: dict, callback: Any) -> None:
    """Transactions go nowhere offline."""
    del transaction, callback


def have_outstanding_v1_account_transactions() -> bool:
    """Never any outstanding transactions."""
    return False


def run_v1_account_transactions() -> None:
    """Nothing to run."""


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

    _babase.pushcall(lambda: call(*args), from_other_thread=True)


# ---------------------------------------------------------------------------
# Attaching offline accounts/cloud to the PlusAppSubsystem.
# ---------------------------------------------------------------------------


def attach(plus: PlusAppSubsystem) -> None:
    """Give a PlusAppSubsystem the parts native plus normally provides."""
    plus.cloud = _make_cloud()
    plus.accounts = _make_accounts()


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

    return OfflineAccountV2Subsystem()
