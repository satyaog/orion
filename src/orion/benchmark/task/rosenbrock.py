#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
:mod:`orion.benchmark.task` -- Task for RosenBrock Function
================================================================

.. module:: task
   :platform: Unix
   :synopsis: Benchmark algorithms with RosenBrock function.

"""
import numpy

from orion.benchmark.base import BaseTask


class RosenBrock(BaseTask):
    """RosenBrock function as benchmark task"""

    def __init__(self, max_trials=20, dim=2):
        self.dim = dim
        super(RosenBrock, self).__init__(max_trials=max_trials, dim=dim)

    def get_blackbox_function(self):
        """
        Return the black box function to optimize, the function will expect hyper-parameters to
        search and return objective values of trial with the hyper-parameters.
        """
        def rosenbrock(x):
            """Evaluate a n-D rosenbrock function."""
            x = numpy.asarray(x)
            summands = 100 * (x[1:] - x[:-1] ** 2) ** 2 + (1 - x[:-1]) ** 2
            y = numpy.sum(summands)
            return [dict(
                name='rosenbrock',
                type='objective',
                value=y)]

        return rosenbrock

    def get_search_space(self):
        """Return the search space for the task objective function"""
        rspace = {'x': 'uniform(-5, 10, shape={})'.format(self.dim)}

        return rspace
