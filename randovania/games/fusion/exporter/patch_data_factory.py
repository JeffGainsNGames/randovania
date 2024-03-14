from __future__ import annotations

from typing import TYPE_CHECKING

from randovania.exporter import pickup_exporter
from randovania.exporter.patch_data_factory import PatchDataFactory
from randovania.game_description.assignment import PickupTarget

# from randovania.games.fusion.exporter.hint_namer import FusionHintNamer
from randovania.games.game import RandovaniaGame
from randovania.generator.pickup_pool import pickup_creator

if TYPE_CHECKING:
    from randovania.exporter.pickup_exporter import ExportedPickupDetails
    from randovania.games.fusion.layout.fusion_configuration import FusionConfiguration
    from randovania.games.fusion.layout.fusion_cosmetic_patches import FusionCosmeticPatches


class FusionPatchDataFactory(PatchDataFactory):
    cosmetic_patches: FusionCosmeticPatches
    configuration: FusionConfiguration

    def game_enum(self) -> RandovaniaGame:
        return RandovaniaGame.FUSION

    def _create_pickup_dict(self, pickup_list: list[ExportedPickupDetails]) -> dict:
        pickup_map_dict = {}
        minor_pickup_list = []
        major_pickup_list = []
        for pickup in pickup_list:
            node = self.game.region_list.node_from_pickup_index(pickup.index)
            is_major = False
            if "source" in node.extra:
                is_major = True

            resource = (
                pickup.conditional_resources[0].resources[-1][0].extra["item"] if not pickup.other_player else "None"
            )
            if is_major:
                major_pickup_list.append({"Source": node.extra["source"], "Item": resource})
            else:
                minor_pickup_list.append(
                    {
                        "Area": self.game.region_list.nodes_to_region(node).extra["area_id"],
                        "Room": self.game.region_list.nodes_to_area(node).extra["room_id"][0],
                        "BlockX": node.extra["blockx"],
                        "BlockY": node.extra["blocky"],
                        "Item": resource,
                        "ItemSprite": pickup.model.name,
                    }
                )
        pickup_map_dict = {"MajorLocations": major_pickup_list, "MinorLocations": minor_pickup_list}
        return pickup_map_dict

    def _create_starting_location(self) -> dict:
        starting_location_node = self.game.region_list.node_by_identifier(self.patches.starting_location)
        starting_location_dict = {
            "Area": self.game.region_list.nodes_to_region(starting_location_node).extra["area_id"],
            "Room": self.game.region_list.nodes_to_area(starting_location_node).extra["room_id"][0],
            "X": starting_location_node.extra["X"],
            "Y": starting_location_node.extra["Y"],
        }
        return starting_location_dict

    def _create_starting_items(self) -> dict:
        starting_dict = {
            "Energy": self.configuration.energy_per_tank - 1,
            "Abilities": [],
            "SecurityLevels": [],
            "DownloadedMaps": [0, 1, 2, 3, 4, 5, 6],
        }
        missile_launcher = next(
            state
            for defi, state in self.configuration.standard_pickup_configuration.pickups_state.items()
            if defi.name == "Missile Launcher Data"
        )
        starting_dict["Missiles"] = missile_launcher.included_ammo[0]
        pb_launcher = next(
            state
            for defi, state in self.configuration.standard_pickup_configuration.pickups_state.items()
            if defi.name == "Power Bomb Data"
        )
        starting_dict["PowerBombs"] = pb_launcher.included_ammo[0]

        for item in self.patches.starting_equipment:
            if "Metroid" in item.name:
                print("skip metroid")
                continue
            pickup_def = next(
                value for key, value in self.pickup_db.standard_pickups.items() if value.name == item.name
            )
            category = pickup_def.extra["StartingItemCategory"]
            # Special Case for E-Tanks
            if category == "Energy":
                starting_dict[category] += self.configuration.energy_per_tank
                continue
            starting_dict[category].append(pickup_def.extra["StartingItemName"])
        return starting_dict

    def _create_tank_increments(self) -> dict:
        tank_dict = {}
        for definition, state in self.patches.configuration.ammo_pickup_configuration.pickups_state.items():
            tank_dict[definition.extra["TankIncrementName"]] = state.ammo_count[0]
        tank_dict["EnergyTank"] = self.configuration.energy_per_tank
        return tank_dict

    def _create_door_locks(self):
        result = []
        for node, weakness in self.patches.all_dock_weaknesses():
            for door, value in enumerate(node.extra["door_idx"]):
                print("area " + str(self.game.region_list.nodes_to_region(node).extra["area_id"]))
                print("room " + str(self.game.region_list.nodes_to_area(node).extra["room_id"][0]))
                print("door " + str(door))
                print("value " + str(value))
                result.append(
                    {
                        "Area": self.game.region_list.nodes_to_region(node).extra["area_id"],
                        "Door": node.extra["door_idx"][door],
                        "LockType": weakness.extra["type"],
                    }
                )
        return result

    def _create_palette(self) -> dict:
        cosmetics = self.cosmetic_patches
        palettes = []
        if cosmetics.enable_suit_palette:
            palettes.append("Samus")
        if cosmetics.enable_beam_palette:
            palettes.append("Beams")
        if cosmetics.enable_enemy_palette:
            palettes.append("Enemies")
        if cosmetics.enable_tileset_palette:
            palettes.append("Tilesets")

        palette_dict = {
            "Randomize": palettes,
            "ColorSpace": cosmetics.color_space.long_name,
        }
        return palette_dict

    def _create_nav_text(self) -> dict:
        return

    def create_data(self) -> dict:
        db = self.game

        useless_target = PickupTarget(
            pickup_creator.create_nothing_pickup(db.resource_database, "Empty"), self.players_config.player_index
        )

        pickup_list = pickup_exporter.export_all_indices(
            self.patches,
            useless_target,
            self.game.region_list,
            self.rng,
            self.configuration.pickup_model_style,
            self.configuration.pickup_model_data_source,
            exporter=pickup_exporter.create_pickup_exporter(
                pickup_exporter.GenericAcquiredMemo(), self.players_config, self.game_enum()
            ),
            visual_nothing=pickup_creator.create_visual_nothing(self.game_enum(), "Anonymous"),
        )

        mars_data = {
            "SeedHash": self.description.shareable_hash,
            "StartingLocation": self._create_starting_location(),
            "StartingItems": self._create_starting_items(),
            "Locations": self._create_pickup_dict(pickup_list),
            "RequiredMetroidCount": self.configuration.artifacts.required_artifacts,
            "TankIncrements": self._create_tank_increments(),
            "DoorLocks": self._create_door_locks(),
            "SkipDoorTransitions": self.configuration.instant_transitions,
            "Palettes": self._create_palette(),
            # "NavigationText": self._create_nav_text(),
        }
        import json

        foo = json.dumps(mars_data)
        print(foo)
        return {}
