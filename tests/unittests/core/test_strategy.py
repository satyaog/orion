#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Collection of tests for :mod:`orion.core.worker.strategies`."""
import pytest

from orion.core.worker.strategies import (Strategy,
                                          MaxParallelStrategy,
                                          MeanParallelStrategy,
                                          NoParallelStrategy)
from orion.core.worker.trial import Trial


@pytest.fixture
def observations():
    points = [i for i in range(10)]
    results = [Trial.Result(name='foo', type='objective', value=points[i])
               for i in range(10)]

    return points, results


@pytest.fixture
def incomplete_trial():
    return Trial(params=[{'name': 'a', 'type': 'integer', 'value': 6}])


class TestStrategyBuild:
    def test_strategy_build_no(self):
        strategy = Strategy.build({
            'of_type': 'NoParallelStrategy',
        })
        assert isinstance(strategy, NoParallelStrategy)


class TestParallelStrategies:
    def test_max_parallel_strategy(self, observations, incomplete_trial):
        points, results = observations

        strategy = MaxParallelStrategy()
        strategy.observe(points, results)
        lying_result = strategy.lie(incomplete_trial)

        objective_results = [result for result in results
                             if result.type == 'objective']
        max_value = max(result.value for result in objective_results)
        assert lying_result.value == max_value

    def test_mean_parallel_strategy(self, observations, incomplete_trial):
        points, results = observations

        strategy = MeanParallelStrategy()
        strategy.observe(points, results)
        lying_result = strategy.lie(incomplete_trial)

        objective_results = [result for result in results
                             if result.type == 'objective']
        mean_value = (sum(result.value for result in objective_results)
                      / float(len(objective_results)))
        assert lying_result.value == mean_value

    def test_no_parallel_strategy(self, observations, incomplete_trial):
        points, results = observations

        strategy = NoParallelStrategy()
        strategy.observe(points, results)
        lying_result = strategy.lie(incomplete_trial)

        assert lying_result == None


