"""
Technology "model" for land-based wind LCOE calculations using ATB data and
Standard Scenarios results.
"""


# All of the computations must be vectorized, so use `numpy`.
import numpy as np


def capital_cost(scale, parameter):
    """Capital cost function."""
    return np.stack([1])


def fixed_cost(scale, parameter):
    """Fixed cost function."""
    return np.stack([1])


def production(scale, capital, lifetime, fixed, input, parameter):
    """Production function."""
    return np.stack([1])



def metrics(scale, capital, lifetime, fixed, input_raw, input, input_price, output_raw, output, cost, parameter):
    """Metrics function."""
    lcoe1 = parameter[0]
    lcoe5 = parameter[1]
    lcoe10 = parameter[2]
    return np.stack([lcoe1, lcoe5, lcoe10])
