from __future__ import annotations

from typing import TYPE_CHECKING

from randovania.game_description.db.pickup_node import PickupNode
from randovania.games.fusion.generator.pool_creator import INFANT_METROID_CATEGORY
from randovania.games.fusion.layout import FusionConfiguration
from randovania.layout.exceptions import InvalidConfiguration
from randovania.resolver.bootstrap import MetroidBootstrap

if TYPE_CHECKING:
    from random import Random

    from randovania.game_description.game_description import GameDescription
    from randovania.game_description.game_patches import GamePatches
    from randovania.games.fusion.layout.fusion_configuration import FusionArtifactConfig
    from randovania.generator.pickup_pool import PoolResults


def all_dna_locations(game: GameDescription, config: FusionArtifactConfig):
    locations = []
    for node in game.region_list.all_nodes:
        if isinstance(node, PickupNode):
            # Metroid pickups
            name = node.pickup_index
            if config.prefer_metroids and name.startswith("oItemDNA_"):
                locations.append(node)
            # Pickups guarded by bosses
            elif config.prefer_bosses and str(name) in _boss_items:
                locations.append(node)

    return locations


class FusionBootstrap(MetroidBootstrap):
    def assign_pool_results(self, rng: Random, patches: GamePatches, pool_results: PoolResults) -> GamePatches:
        assert isinstance(patches.configuration, FusionConfiguration)
        config = patches.configuration.artifacts

        if config.prefer_anywhere:
            return super().assign_pool_results(rng, patches, pool_results)

        locations = all_dna_locations(patches.game, config)
        rng.shuffle(locations)

        dna_to_assign = [
            pickup for pickup in list(pool_results.to_place) if pickup.pickup_category is INFANT_METROID_CATEGORY
        ]

        if len(dna_to_assign) > len(locations):
            raise InvalidConfiguration(
                f"Has {len(dna_to_assign)} Infant Metroids in the pool, but only {len(locations)} valid locations."
            )

        for dna, location in zip(dna_to_assign, locations, strict=False):
            pool_results.to_place.remove(dna)
            pool_results.assignment[location.pickup_index] = dna

        return super().assign_pool_results(rng, patches, pool_results)


_boss_items = [
    "PickupIndex 100",
    "PickupIndex 106",
    "PickupIndex 114",
    "PickupIndex 104",
    "PickupIndex 115",
    "PickupIndex 107",
    "PickupIndex 110",
    "PickupIndex 102",
    "PickupIndex 109",
    "PickupIndex 108",
    "PickupIndex 111",
]
