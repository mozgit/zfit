#  Copyright (c) 2020 zfit
from collections import OrderedDict
from typing import Mapping

import numpy as np
import tensorflow as tf
import tensorflow_probability as tfp

from .baseminimizer import BaseMinimizer, print_gradients, ZfitStrategy, print_params
from .fitresult import FitResult
from .. import z


class BFGS(BaseMinimizer):

    def __init__(self, strategy: ZfitStrategy = None, tolerance: float = 1e-5, verbosity: int = 5,
                 max_calls: int = 3000,
                 name: str = "BFGS_TFP", options: Mapping = None) -> None:
        """

        Args:
            strategy (ZfitStrategy): Strategy that handles NaN and more (to come, experimental)
            tolerance (float): Difference between the function value that suffices to stop minimization
            verbosity: The higher, the more is printed. Between 1 and 10 typically
            max_calls (int): Maximum number of calls, approximate
            name: Name of the Minimizer
            options: A `dict` containing the options given to the minimization function, overriding the default
        """
        self.options = {} if options is None else options
        self.max_calls = max_calls
        super().__init__(strategy=strategy, tolerance=tolerance, verbosity=verbosity, name=name,
                         minimizer_options={})

    def _minimize(self, loss, params):
        minimizer_fn = tfp.optimizer.bfgs_minimize
        params = tuple(params)
        do_print = self.verbosity > 8

        current_loss = None
        nan_counter = 0

        # @z.function
        def update_params_value_grad(loss, params, values):
            for param, value in zip(params, tf.unstack(values, axis=0)):
                param.set_value(value)
            value, gradients = loss.value_gradients(params=params)
            return gradients, value

        def to_minimize_func(values):
            nonlocal current_loss, nan_counter
            do_print = self.verbosity > 8

            is_nan = False
            gradients = None
            value = None
            try:
                gradients, value = update_params_value_grad(loss, params, values)

            except tf.errors.InvalidArgumentError:
                err = 'NaNs'
                is_nan = True
            except:
                err = 'unknonw error'
                raise
            finally:
                if value is None:
                    value = f"invalid, {err}"
                if gradients is None:
                    gradients = [f"invalid, {err}"] * len(params)
                if do_print:
                    print_gradients(params, values.numpy(), [float(g.numpy()) for g in gradients], loss=value.numpy())
            loss_evaluated = value.numpy()
            is_nan = is_nan or np.isnan(loss_evaluated)
            if is_nan:
                nan_counter += 1
                info_values = {}
                info_values['loss'] = value.numpy()
                info_values['old_loss'] = current_loss
                info_values['nan_counter'] = nan_counter
                value = self.strategy.minimize_nan(loss=loss, params=params, minimizer=self,
                                                   values=info_values)
            else:
                nan_counter = 0
                current_loss = value

            gradients = tf.stack(gradients)
            return value, gradients

        initial_inv_hessian_est = tf.linalg.tensor_diag([p.step_size for p in params])

        minimizer_kwargs = dict(
            initial_position=tf.stack(params),
            x_tolerance=self.tolerance,
            # f_relative_tolerance=self.tolerance * 1e-5,  # TODO: use edm for stopping criteria
            initial_inverse_hessian_estimate=initial_inv_hessian_est,
            parallel_iterations=1,
            max_iterations=self.max_calls
        )
        minimizer_kwargs.update(self.options)
        result = minimizer_fn(to_minimize_func,
                              **minimizer_kwargs)

        # save result
        params_result = result.position.numpy()
        self._update_params(params, values=params_result)

        info = {'n_eval': result.num_objective_evaluations.numpy(),
                'n_iter': result.num_iterations.numpy(),
                'grad': result.objective_gradient.numpy(),
                'original': result}
        edm = -999
        fmin = result.objective_value.numpy()
        status = -999
        converged = result.converged.numpy()
        params = OrderedDict((p, val) for p, val in zip(params, params_result))
        result = FitResult(params=params, edm=edm, fmin=fmin, info=info, loss=loss,
                           status=status, converged=converged,
                           minimizer=self.copy())
        return result
