# This file is part of GridCal.
#
# GridCal is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GridCal is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GridCal.  If not, see <http://www.gnu.org/licenses/>.

import pandas as pd
import numpy as np
import json
from matplotlib import pyplot as plt

from PySide2.QtCore import QThread, Signal

from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import power_flow_post_process, PowerFlowOptions
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Simulations.ContinuationPowerFlow.continuation_power_flow import continuation_nr, VCStopAt, VCParametrization
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Core.snapshot_pf_data import compile_snapshot_circuit, split_into_islands
from GridCal.Engine.plot_config import LINEWIDTH
from GridCal.Gui.GuiFunctions import ResultsModel


########################################################################################################################
# Voltage collapse classes
########################################################################################################################


class VoltageCollapseOptions:

    def __init__(self, step=0.01, approximation_order=VCParametrization.Natural, adapt_step=True, step_min=0.0001,
                 step_max=0.2, error_tol=1e-3, tol=1e-6, max_it=20, stop_at=VCStopAt.Nose, verbose=False):
        """
        Voltage collapse options
        @param step: Step length
        @param approximation_order: Order of the approximation: 1, 2, 3, etc...
        @param adapt_step: Use adaptive step length?
        @param step_min: Minimum step length
        @param step_max: Maximum step length
        @param error_tol: Error tolerance
        @param tol: tolerance
        @param max_it: Maximum number of iterations
        @param stop_at: Value of lambda to stop at, it can be specified by a concept namely NOSE to sto at the edge or
        FULL tp draw the full curve
        """

        self.step = step

        self.approximation_order = approximation_order

        self.adapt_step = adapt_step

        self.step_min = step_min

        self.step_max = step_max

        self.error_tol = error_tol

        self.tol = tol

        self.max_it = max_it

        self.stop_at = stop_at

        self.verbose = verbose


class VoltageCollapseInput:

    def __init__(self, Sbase, Vbase, Starget):
        """
        VoltageCollapseInput constructor
        @param Sbase: Initial power array
        @param Vbase: Initial voltage array
        @param Starget: Final power array
        """
        self.Sbase = Sbase

        self.Starget = Starget

        self.Vbase = Vbase


class VoltageCollapseResults:

    def __init__(self, nbus, nbr, bus_names):
        """
        VoltageCollapseResults instance
        :param nbus: number of buses
        :param nbr: number of branches
        :param bus_names: names of the buses
        """

        self.name = 'Voltage collapse'

        self.bus_names = bus_names

        self.voltages = None

        self.lambdas = None

        self.error = None

        self.converged = False

        self.Sbranch = np.zeros(nbr, dtype=complex)

        self.Ibranch = np.zeros(nbr, dtype=complex)

        self.loading = np.zeros(nbr, dtype=complex)

        self.losses = np.zeros(nbr, dtype=complex)

        self.Sbus = np.zeros(nbus, dtype=complex)

        self.bus_types = np.zeros(nbus, dtype=int)

        self.available_results = [ResultTypes.BusVoltage]

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'lambda': self.lambdas.tolist(),
                'Vm': np.abs(self.voltages).tolist(),
                'Va': np.angle(self.voltages).tolist(),
                'error': self.error.tolist()}
        return data

    def save(self, fname):
        """
        Export as json file
        """
        with open(fname, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def apply_from_island(self, voltage_collapse_res, Sbranch, Ibranch, loading, losses, Sbus,
                          bus_original_idx, branch_original_idx, nbus_full):
        """
        Apply the results of an island to this VoltageCollapseResults instance
        :param voltage_collapse_res: VoltageCollapseResults instance of the island
        :param bus_original_idx: indices of the buses in the complete grid
        :param branch_original_idx: indices of the branches in the complete grid
        :param nbus_full: total number of buses in the complete grid
        """

        if len(voltage_collapse_res.voltages) > 0:

            n_lambda, n_bus = voltage_collapse_res.voltages.shape

            if self.voltages is None:
                # fill a matrix with the values of the (eligibly) first island
                self.voltages = np.zeros((n_lambda, nbus_full), dtype=complex)
                self.voltages[:, bus_original_idx] = voltage_collapse_res.voltages
                self.lambdas = voltage_collapse_res.lambdas
            else:
                # if the voltages are not none, that means that another island initialized the voltages.
                # We know that the number of nodes is the total number of nodes, but the number of lambda-steps might
                # be different. Hence we need to copy the new island voltages accordingly
                l_prev = self.voltages.shape[0]

                if n_lambda > l_prev:
                    # now there are more rows than before, hence we need to extend
                    voltages_before = self.voltages.copy()

                    # re-initialize the voltages array
                    self.voltages = np.zeros((n_lambda, nbus_full), dtype=complex)

                    # copy the old voltages to the empty voltages array
                    self.voltages[0:l_prev, :] = voltages_before

                    # copy the new voltages
                    self.voltages[:, bus_original_idx] = voltage_collapse_res.voltages

                    # now there are more values of lambda, just use the new ones
                    self.lambdas = voltage_collapse_res.lambdas

                elif n_lambda < l_prev:
                    # the number of lambda values in this island is lower, so just copy at the beginning
                    self.voltages[0:n_lambda, bus_original_idx] = voltage_collapse_res.voltages
                else:
                    # same number of lambda values, just copy where needed
                    self.voltages[:, bus_original_idx] = voltage_collapse_res.voltages

            # set the branch values
            self.Sbranch[branch_original_idx] = Sbranch
            self.Ibranch[branch_original_idx] = Ibranch
            self.loading[branch_original_idx] = loading
            self.losses[branch_original_idx] = losses
            self.Sbus[bus_original_idx] = Sbus

    def mdl(self, result_type: ResultTypes = ResultTypes.BusVoltage) -> ResultsModel:
        """
        Plot the results
        :param result_type:
        :return:
        """

        labels = self.bus_names
        y_label = ''
        x_label = ''
        title = ''
        if result_type == ResultTypes.BusVoltage:
            y = abs(np.array(self.voltages))
            x = self.lambdas
            title = 'Bus voltage'
            y_label = '(p.u.)'
            x_label = 'Loading from the base situation ($\lambda$)'
        else:
            x = self.lambdas
            y = self.voltages

        # assemble model
        mdl = ResultsModel(data=y, index=x, columns=labels, title=title,
                           ylabel=y_label, xlabel=x_label, units=y_label)
        return mdl


class VoltageCollapse(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Voltage Stability'

    def __init__(self, circuit: MultiCircuit, options: VoltageCollapseOptions, inputs: VoltageCollapseInput,
                 pf_options: PowerFlowOptions, opf_results=None):
        """
        VoltageCollapse constructor
        @param circuit: NumericalCircuit instance
        @param options:
        """
        QThread.__init__(self)

        # MultiCircuit instance
        self.circuit = circuit

        # voltage stability options
        self.options = options

        self.inputs = inputs

        self.pf_options = pf_options

        self.opf_results = opf_results

        self.results = list()

        self.__cancel__ = False

    def get_steps(self):
        """
        List of steps
        """
        if self.results.lambdas is not None:
            return ['Lambda:' + str(l) for l in self.results.lambdas]
        else:
            return list()

    def progress_callback(self, l):
        """
        Send progress report
        :param l: lambda value
        :return: None
        """
        self.progress_text.emit('Running voltage collapse lambda:' + "{0:.2f}".format(l) + '...')

    def run(self):
        """
        run the voltage collapse simulation
        @return:
        """
        print('Running voltage collapse...')
        nbus = self.circuit.get_bus_number()

        numerical_circuit = compile_snapshot_circuit(circuit=self.circuit,
                                                     apply_temperature=self.pf_options.apply_temperature_correction,
                                                     branch_tolerance_mode=self.pf_options.branch_impedance_tolerance_mode,
                                                     opf_results=self.opf_results)

        numerical_input_islands = split_into_islands(numeric_circuit=numerical_circuit,
                                                     ignore_single_node_islands=self.pf_options.ignore_single_node_islands)

        self.results = VoltageCollapseResults(nbus=numerical_circuit.nbus,
                                              nbr=numerical_circuit.nbr,
                                              bus_names=numerical_circuit.bus_names)

        self.results.bus_types = numerical_circuit.bus_types

        for nc, numerical_island in enumerate(numerical_input_islands):

            self.progress_text.emit('Running voltage collapse at circuit ' + str(nc) + '...')

            if len(numerical_island.vd) > 0:
                Voltage_series, Lambda_series, \
                normF, success = continuation_nr(Ybus=numerical_island.Ybus,
                                                 Ibus_base=numerical_island.Ibus,
                                                 Ibus_target=numerical_island.Ibus,
                                                 Sbus_base=self.inputs.Sbase[numerical_island.original_bus_idx],
                                                 Sbus_target=self.inputs.Starget[numerical_island.original_bus_idx],
                                                 V=self.inputs.Vbase[numerical_island.original_bus_idx],
                                                 pv=numerical_island.pv,
                                                 pq=numerical_island.pq,
                                                 step=self.options.step,
                                                 approximation_order=self.options.approximation_order,
                                                 adapt_step=self.options.adapt_step,
                                                 step_min=self.options.step_min,
                                                 step_max=self.options.step_max,
                                                 error_tol=self.options.error_tol,
                                                 tol=self.options.tol,
                                                 max_it=self.options.max_it,
                                                 stop_at=self.options.stop_at,
                                                 verbose=False,
                                                 call_back_fx=self.progress_callback)

                # nbus can be zero, because all the arrays are going to be overwritten
                res = VoltageCollapseResults(nbus=numerical_island.nbus,
                                             nbr=numerical_island.nbr,
                                             bus_names=numerical_island.bus_names)
                res.voltages = np.array(Voltage_series)
                res.lambdas = np.array(Lambda_series)
                res.error = normF
                res.converged = bool(success)
            else:
                res = VoltageCollapseResults(nbus=numerical_island.nbus,
                                             nbr=numerical_island.nbr,
                                             bus_names=numerical_island.bus_names)
                res.voltages = np.array([[0] * numerical_island.nbus])
                res.lambdas = np.array([[0] * numerical_island.nbus])
                res.error = [0]
                res.converged = True

            if len(res.voltages) > 0:
                # compute the island branch results
                Sbranch, Ibranch, Vbranch, \
                loading, losses, flow_direction, \
                Sbus = power_flow_post_process(calculation_inputs=numerical_island,
                                               Sbus=self.inputs.Starget[numerical_island.original_bus_idx],
                                               V=res.voltages[-1],
                                               branch_rates=numerical_island.branch_rates)

                # update results
                self.results.apply_from_island(voltage_collapse_res=res,
                                               Sbranch=Sbranch,
                                               Ibranch=Ibranch,
                                               loading=loading,
                                               losses=losses,
                                               Sbus=Sbus,
                                               bus_original_idx=numerical_island.original_bus_idx,
                                               branch_original_idx=numerical_island.original_branch_idx,
                                               nbus_full=nbus)
            else:
                print('No voltage values!')
        print('done!')
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        self.__cancel__ = True
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()

