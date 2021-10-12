#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Tests tod world, notably for batching.
"""

import copy
import unittest

import parlai.core.tod.tod_test_utils.agents_and_teachers as aat
import parlai.scripts.tod_world_script as tod_world_script
from parlai.core.tod.tod_agents_and_teachers import TodStandaloneApiAgent
from parlai.core.tod.impl.world_metrics_handlers import (
    METRICS_HANDLER_CLASSES_TEST_REGISTRY,
)
from parlai.core.metrics import dict_report


class TestTodWorldScript(tod_world_script.TodWorldScript):
    """
    Wrap around it to check its logic; also makes it easier to do things w/ underlying
    World.
    """

    def _get_tod_agents(self, opt):
        """
        Hack so we can separate out logic of making sure agent parsing is correct.
        """
        if hasattr(self, "agents"):
            return self.agents
        return super()._get_tod_agents(opt)

    def _setup_world(self):
        world = super()._setup_world()
        for i in range(len(world.batch_tod_world_metrics)):
            world.batch_tod_world_metrics[i].handlers = [
                x() for x in METRICS_HANDLER_CLASSES_TEST_REGISTRY
            ]
        return world

    def _save_outputs(self, opt, world, logger, episode_metrics):
        self.world = world
        self.episode_metrics = episode_metrics


class TodWorldInScriptTestBase(unittest.TestCase):
    def add_tod_world_opts(self, base_opts):
        """
        Convenience since we're initing the opt directly without parlai parser.
        """
        opts = copy.deepcopy(base_opts)
        opts["datatype"] = "DUMMY"
        opts["datafile"] = "DUMMY"
        opts["episodes_randomization_seed"] = 32  # test it!
        opts["standalone_api_file"] = aat.API_DATABASE_FILE
        opts["exact_api_call"] = True
        opts["log_keep_fields"] = "all"
        opts["display_examples"] = False
        opts[
            "include_api_schemas"
        ] = True  # do this to aat.make sure they're done correctly.
        return opts

    def setup_agents(self, added_opts):
        full_opts = self.add_tod_world_opts(added_opts)
        sys = aat.ApiCallAndSysUttAgent(full_opts)
        agents = [
            aat.UserUttAgent(full_opts),
            sys,
            TodStandaloneApiAgent(full_opts),
            sys,
            aat.ApiSchemaAgent(full_opts),
            aat.GoalAgent(full_opts),
        ]
        return agents, full_opts

    def _run_test(self):
        self._run_test_helper(aat.EPISODE_SETUP__SINGLE_API_CALL)
        self._run_test_helper(aat.EPISODE_SETUP__MULTI_ROUND)
        self._run_test_helper(aat.EPISODE_SETUP__MULTI_EPISODE)
        self._run_test_helper(aat.EPISODE_SETUP__MULTI_EPISODE_BS)

    def _run_test_helper(self, config_base):
        config = copy.deepcopy(config_base)
        config["use_broken_mock_api_calls"] = True
        add = self.config_args()
        for key in add:
            config[key] = add[key]
        agents, opt = self.setup_agents(config)
        script = TestTodWorldScript(opt)
        script.agents = agents
        script.run()
        self._check_metrics_correct(script, opt)

    def _check_metrics_correct(self, script, opt):
        """
        Last argument is only relevant for the max_turn test.
        """
        max_rounds = opt[aat.TEST_NUM_ROUNDS_OPT_KEY]
        max_episodes = opt[aat.TEST_NUM_EPISODES_OPT_KEY]
        episode_metrics = script.episode_metrics
        for episode_idx, episode in enumerate(episode_metrics):
            #        if episode_idx >= max_episodes:
            #            break
            # See how we make broken mock api calls in the aat.
            goal, episode_metric = episode
            episode_metric = dict_report(episode_metric.report())
            self.assertAlmostEqual(
                episode_metric["all_goals_hit"],
                not aat.episode_has_broken_api_turn(episode_idx, max_rounds),
            )
        broken_episodes = sum(
            [
                aat.episode_has_broken_api_turn(i, max_rounds)
                for i in range(max_episodes)
            ]
        )
        report = dict_report(script.world.report())
        self.assertAlmostEqual(
            report["all_goals_hit"],
            float(max_episodes - broken_episodes) / max_episodes,
        )


class TodWorldSingleBatchTest(TodWorldInScriptTestBase):
    def config_args(self):
        config = {}
        config["batchsize"] = 1
        config["max_turns"] = 10
        return config

    def test_metricsCorrect(self):
        self._run_test()


class TodWorldNonSingleBatchTest(TodWorldInScriptTestBase):
    def config_args(self):
        config = {}
        config["batchsize"] = 4
        config["max_turns"] = 10
        return config

    def test_metricsCorrect(self):
        self._run_test()


if __name__ == "__main__":
    unittest.main()
