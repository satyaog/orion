# TODO move model stuff from lpi to analysis.base
import copy
import itertools

import pandas
import numpy

from orion.analysis.base import flatten_params, train_regressor, to_numpy, flatten_numpy

from orion.core.worker.transformer import build_required_space


def partial_dependency(
    trials,
    space,
    params=None,
    model="RandomForestRegressor",
    n_grid_points=10,
    n_samples=40,
    **kwargs
):
    """
    Calculates the partial dependency of parameters in a collection of :class:`Trial`.

    Parameters
    ----------
    trials: DataFrame or dict
        A dataframe of trials containing, at least, the columns 'objective' and 'id'. Or a dict
        equivalent.

    space: Space object
        A space object from an experiment.

    params: list of str, optional
        The parameters to include in the computation. All parameters are included by default.

    model: str
        Name of the regression model to use. Can be one of
        - AdaBoostRegressor
        - BaggingRegressor
        - ExtraTreesRegressor
        - GradientBoostingRegressor
        - RandomForestRegressor (Default)

    n_grid_points: int
        Number of points in the grid to compute partial dependency. Default is 20.

    n_samples: int
        Number of samples to randomly generate the grid used to compute the partial dependency.

    **kwargs
        Arguments for the regressor model.

    Returns
    -------
    dict
        Dictionary of DataFrames. Each combination of parameters as keys (dim1.name, dim2.name)
        and for each parameters individually (dim1.name). Columns are
        (dim1.name, dim2.name, objective) or (dim1.name, objective).

    """
    params = flatten_params(space, params)

    flattened_space = build_required_space(
        space,
        dist_requirement="linear",
        type_requirement="numerical",
        shape_requirement="flattened",
    )

    if trials.empty or trials.shape[0] == 0:
        return {}

    data = to_numpy(trials, space)
    data = flatten_numpy(data, flattened_space)
    model = train_regressor(model, data, **kwargs)

    data = flattened_space.sample(n_samples)
    data = pandas.DataFrame(data, columns=flattened_space.keys())

    partial_dependencies = dict()
    for x_i in range(len(params)):
        grid, averages, stds = partial_dependency_grid(
            flattened_space, model, [params[x_i]], data, n_grid_points
        )
        grid = reverse(flattened_space, grid)
        partial_dependencies[params[x_i]] = (grid, averages, stds)
        for y_i in range(x_i + 1, len(params)):
            grid, averages, stds = partial_dependency_grid(
                flattened_space, model, [params[x_i], params[y_i]], data, n_grid_points
            )
            grid = reverse(flattened_space, grid)
            partial_dependencies[(params[x_i], params[y_i])] = (grid, averages, stds)

    return partial_dependencies


def reverse(transformed_space, grid):
    """Reverse transformations on the grid to bring back to original space"""
    for param in grid.keys():
        transformed_dim = transformed_space[param].original_dimension
        param_grid = []
        for i, e in enumerate(grid[param]):
            param_grid.append(transformed_dim.reverse(e))
        grid[param] = param_grid
    return grid


def make_grid(dim, n_points):
    """Build a grid of n_points for a dim"""
    if dim.prior_name == "choices":
        low, high = dim.interval()
        return numpy.arange(low, high + 1)

    return numpy.linspace(*dim.interval(), num=n_points)


def partial_dependency_grid(space, model, params, samples, n_points=40):

    samples = copy.deepcopy(samples)

    grids = {}
    for name in params:
        grids[name] = make_grid(space[name], n_points)

    lengths = [len(grids[name]) for name in params]
    averages = numpy.zeros(lengths)
    stds = numpy.zeros(lengths)

    indexed_combinations = zip(
        itertools.product(*(list(range(length)) for length in lengths)),
        itertools.product(*grids.values()),
    )
    for z_idx, combination in indexed_combinations:
        for i, name in enumerate(params):
            samples[name] = combination[i]

        predictions = model.predict(samples.to_numpy())
        averages[z_idx] = numpy.mean(predictions)
        stds[z_idx] = numpy.std(predictions)

    return grids, averages.T, stds.T
