"""
:mod:`orion.algo.pb2.pb2
========================

"""
import logging
import time

import numpy as np
import pandas
from orion.algo.pbt.pbt import PBT
from orion.core.worker.trial import Trial

from orion.algo.pb2.pb2_utils import select_config

logger = logging.getLogger(__name__)
from orion.core.utils.flatten import flatten


class PB2(PBT):
    """TODO: Class docstring

    Parameters
    ----------
    space: `orion.algo.space.Space`
        Optimisation space with priors for each dimension.
    seed: None, int or sequence of int
        Seed for the random number generator used to sample new trials.
        Default: ``None``

    """

    requires_type = "real"
    requires_dist = "linear"
    requires_shape = "flattened"

    def __init__(
        self,
        space,
        seed=None,
        population_size=50,
        generations=10,
        exploit=None,
        fork_timeout=60,
    ):
        super(PB2, self).__init__(
            space,
            seed=seed,
            population_size=population_size,
            generations=generations,
            exploit=exploit,
            fork_timeout=fork_timeout,
        )

    @property
    def configuration(self):
        """Return tunable elements of this algorithm in a dictionary form
        appropriate for saving.

        """
        config = super(PB2, self).configuration
        config["pb2"].pop("explore")
        return config

    def _generate_offspring(self, trial):
        """Try to promote or fork a given trial."""

        new_trial = trial

        if not self.has_suggested(new_trial):
            raise RuntimeError(
                "Trying to fork a trial that was not registered yet. This should never happen"
            )

        attempts = 0
        start = time.perf_counter()
        while (
            self.has_suggested(new_trial)
            and time.perf_counter() - start <= self.fork_timeout
        ):
            trial_to_explore = self.exploit_func(
                self.rng,
                trial,
                self.lineages,
            )

            if trial_to_explore is None:
                return None, None
            elif trial_to_explore is trial:
                new_params = {}
                trial_to_branch = trial
                logger.debug("Promoting trial %s, parameters stay the same.", trial)
            else:
                new_params = flatten(self._explore(self.space, trial_to_explore))
                trial_to_branch = trial_to_explore
                logger.debug(
                    "Forking trial %s with new parameters %s",
                    trial_to_branch,
                    new_params,
                )

            # Set next level of fidelity
            new_params[self.fidelity_index] = self.fidelity_upgrades[
                trial_to_branch.params[self.fidelity_index]
            ]

            new_trial = trial_to_branch.branch(params=new_params)
            new_trial = self.space.transform(self.space.reverse(new_trial))

            logger.debug("Attempt %s - Creating new trial %s", attempts, new_trial)

            attempts += 1

        if (
            self.has_suggested(new_trial)
            and time.perf_counter() - start > self.fork_timeout
        ):
            raise RuntimeError(
                f"Could not generate unique new parameters for trial {trial.id} in "
                f"less than {self.fork_timeout} seconds. Attempted {attempts} times."
            )

        return trial_to_branch, new_trial

    def _explore(self, space, base: Trial):
        """Generate new hyperparameters for given trial.

        Derived from PB2 explore implementation in Ray (2022/02/18):
        https://github.com/ray-project/ray/blob/master/python/ray/tune/schedulers/pb2.py#L131
        """

        data, current = self._get_data_and_current()
        bounds = {dim.name: dim.interval() for dim in space.values()}

        df = data.copy()

        # Group by trial ID and hyperparams.
        # Compute change in timesteps and reward.
        diff_reward = (
            df.groupby(["Trial"] + list(bounds.keys()))["Reward"]
            .mean()
            .diff()
            .reset_index(drop=True)
        )
        df["y"] = diff_reward

        df["R_before"] = df.Reward - df.y

        df = df[~df.y.isna()].reset_index(drop=True)

        # Only use the last 1k datapoints, so the GP is not too slow.
        df = df.iloc[-1000:, :].reset_index(drop=True)

        # We need this to know the T and Reward for the weights.
        if not df[df["Trial"] == self.get_id(base)].empty:
            # N ow specify the dataset for the GP.
            y_raw = np.array(df.y.values)
            # Meta data we keep -> episodes and reward.
            t_r = df[["Budget", "R_before"]]
            hparams = df[bounds.keys()]
            x_raw = pandas.concat([t_r, hparams], axis=1).values
            newpoint = (
                df[df["Trial"] == self.get_id(base)]
                .iloc[-1, :][["Budget", "R_before"]]
                .values
            )
            new = select_config(
                x_raw, y_raw, current, newpoint, bounds, num_f=len(t_r.columns)
            )

            new_config = base.params.copy()
            for i, col in enumerate(hparams.columns):
                if isinstance(base.params[col], int):
                    new_config[col] = int(new[i])
                else:
                    new_config[col] = new[i]

        else:
            new_config = base.params

        return new_config

    def _get_data_and_current(self):
        """Generate data and current objects used in _explore function.

        data is a pandas DataFrame combining data from all completed trials.
        current is a numpy array with hyperparameters from uncompleted trials.
        """
        data_trials = []
        current_trials = []
        for _, (trial, _) in self._trials_info.items():
            if trial.status == "completed":
                data_trials.append(trial)
            else:
                current_trials.append(trial)
        data = self._trials_to_data(data_trials)
        if current_trials:
            current = np.asarray(
                [
                    [trial.params[key] for key in self.space.keys()]
                    for trial in current_trials
                ]
            )
        else:
            current = None
        return data, current

    def _trials_to_data(self, trials):
        """Generate data frame to use in _explore method."""
        rows = []
        cols = ["Trial", "Budget"] + list(self.space.keys()) + ["Reward"]
        for trial in trials:
            values = [trial.params[key] for key in self.space.keys()]
            lst = (
                [self.get_id(trial), trial.params[self.fidelity_index]]
                + values
                + [trial.objective.value]
            )
            rows.append(lst)
        data = pandas.DataFrame(rows, columns=cols)
        data.Trial = data.Trial.astype("str")
        return data
