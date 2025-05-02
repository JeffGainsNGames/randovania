import logging
import uuid

from qasync import asyncSlot

from randovania.game.game_enum import RandovaniaGame
from randovania.game_connection.connector.remote_connector import (
    RemoteConnector,
)
from randovania.game_connection.executor.fusion_executor import FusionExecutor
from randovania.game_description import default_database
from randovania.game_description.db.region import Region
from randovania.game_description.resources.inventory import Inventory
from randovania.network_common.remote_pickup import RemotePickup


class FusionRemoteConnector(RemoteConnector):
    _game_enum: RandovaniaGame = RandovaniaGame.FUSION

    def __init__(self, executor: FusionExecutor):
        super().__init__()
        self._layout_uuid = uuid.UUID(executor.layout_uuid_str)
        self.logger = logging.getLogger(type(self).__name__)
        self.executor = executor
        self.game = default_database.game_description_for(RandovaniaGame.FUSION)

        self.reset_values()

        self.executor.signals.new_inventory.connect(self.new_inventory_received)
        self.executor.signals.new_collected_locations.connect(self.new_collected_locations_received)
        self.executor.signals.new_player_location.connect(self.new_player_location_received)
        self.executor.signals.new_received_pickups.connect(self.new_received_pickups_received)
        self.executor.signals.connection_lost.connect(self.connection_lost)

    @property
    def game_enum(self) -> RandovaniaGame:
        return self._game_enum

    def description(self) -> str:
        return f"{self.game_enum.long_name}"

    async def current_game_status(self) -> tuple[bool, Region | None]:
        return (self.in_cooldown, self.current_region)

    def connection_lost(self) -> None:
        self.logger.info("Finishing connector")

    async def force_finish(self) -> None:
        self.executor.disconnect()

    def is_disconnected(self) -> bool:
        return not self.executor.is_connected()

    # Reset all values on init, disconnect or after switching back to main menu
    def reset_values(self) -> None:
        self.remote_pickups: tuple[RemotePickup, ...] = ()
        self.last_inventory = Inventory.empty()
        self.in_cooldown = True
        self.received_pickups: int | None = None
        self.current_region: Region | None = None

    def new_player_location_received(self, state_or_region: str) -> None:
        pass

    def new_collected_locations_received(self, new_indices_response: str) -> None:
        pass

    def new_inventory_received(self, new_inventory_response: str) -> None:
        pass

    @asyncSlot()
    async def new_received_pickups_received(self, new_received_pickups: str) -> None:
        pass

    async def set_remote_pickups(self, remote_pickups: tuple[RemotePickup, ...]) -> None:
        self.remote_pickups = remote_pickups
        await self.receive_remote_pickups()

    async def receive_remote_pickups(self) -> None:
        """
        If game is missing pickups, send them to it.
        """
        remote_pickups = self.remote_pickups

        # In this case, the game never communicated with us properly with how many items it had.
        if self.received_pickups is None:
            return

        # Early exit, if we can't send anything to the game, or if we don't need to send it items.
        num_pickups = self.received_pickups
        if num_pickups >= len(remote_pickups) or self.in_cooldown:
            return

        # Mark as cooldown, and send provider, item name, model name and quantity to game
        self.in_cooldown = True
        provider_name, pickup, coop_location = remote_pickups[num_pickups]
        name, model = pickup.name, pickup.model.name
        # For some reason, the resources here are sorted differently to the patch data factory.
        # There we want the first entry, here we want the last.
        quantity = next(pickup.conditional_resources).resources[-1][1]

        self.logger.debug("Resource changes for %s from %s", pickup.name, provider_name)
        await self.executor.send_pickup_info(provider_name, name, model, quantity, num_pickups + 1)

    async def display_arbitrary_message(self, message: str) -> None:
        escaped_message = message.replace("#", "\\#")  # In GameMaker, '#' is a newline.
        await self.executor.display_message(escaped_message)
