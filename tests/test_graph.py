#  Copyright (c) 2020 zfit

import tensorflow as tf

import zfit
from zfit import z
# noinspection PyUnresolvedReferences
from zfit.core.testing import setup_function, teardown_function, tester


def test_modes():
    counts = 0

    @z.function(wraps='42')
    def func(x):
        nonlocal counts
        counts += 1
        return tf.random.uniform(shape=()) * x

    func(5)
    func(5)
    func(5)
    func(5)
    assert counts == 1
    zfit.run.set_mode(graph=False)
    func(5)
    assert counts == 2
    zfit.run.set_mode_default()
    func(5)
    func(5)
    func(5)
    assert counts == 2
    zfit.run.clear_graph_cache()
    func(5)
    func(5)
    func(5)
    assert counts == 3

    zfit.run.set_mode(autograd=False)
    assert zfit.settings.options.numerical_grad
    zfit.run.set_mode_default()
    assert not zfit.settings.options.numerical_grad
