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

import json
import pandas as pd
import numpy as np
import time
import multiprocessing
from sklearn.cluster import KMeans
from PySide2.QtCore import QThread, QThreadPool, Signal

from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
from GridCal.Engine.Simulations.result_types import ResultTypes
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import single_island_pf, power_flow_worker_args
from GridCal.Engine.Core.time_series_pf_data import compile_time_circuit, BranchImpedanceMode
from GridCal.Engine.Simulations.Stochastic.latin_hypercube_sampling import lhs
from GridCal.Engine.Simulations.results_model import ResultsModel


class TimeSeriesClusteringResults(PowerFlowResults):

    def __init__(self, n, m, n_tr, n_hvdc, bus_names, branch_names, transformer_names, hvdc_names,
                 time_array, bus_types):
        """
        TimeSeriesResults constructor
        :param n: number of buses
        :param m: number of branches
        :param n_tr:
        :param n_hvdc:
        :param bus_names:
        :param branch_names:
        :param transformer_names:
        :param hvdc_names:
        :param time_array:
        :param bus_types:
        """
        PowerFlowResults.__init__(self,
                                  n=n,
                                  m=m,
                                  n_tr=n_tr,
                                  n_hvdc=n_hvdc,
                                  bus_names=bus_names,
                                  branch_names=branch_names,
                                  transformer_names=transformer_names,
                                  hvdc_names=hvdc_names,
                                  bus_types=bus_types)

        self.name = 'Time series'
        self.nt = len(time_array)
        self.m = m
        self.n = n

        self.time = time_array

        self.bus_types = np.zeros(n, dtype=int)

        self.voltage = np.zeros((self.nt, n), dtype=complex)

        self.S = np.zeros((self.nt, n), dtype=complex)

        self.Sf = np.zeros((self.nt, m), dtype=complex)

        self.St = np.zeros((self.nt, m), dtype=complex)

        self.Vbranch = np.zeros((self.nt, m), dtype=complex)

        self.loading = np.zeros((self.nt, m), dtype=complex)

        self.losses = np.zeros((self.nt, m), dtype=complex)

        self.hvdc_losses = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_Pf = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_Pt = np.zeros((self.nt, self.n_hvdc))

        self.hvdc_loading = np.zeros((self.nt, self.n_hvdc))

        self.flow_direction = np.zeros((self.nt, m), dtype=float)

        self.error_values = np.zeros(self.nt)

        self.converged_values = np.ones(self.nt, dtype=bool)  # guilty assumption

        self.overloads = [None] * self.nt

        self.overvoltage = [None] * self.nt

        self.undervoltage = [None] * self.nt

        self.overloads_idx = [None] * self.nt

        self.overvoltage_idx = [None] * self.nt

        self.undervoltage_idx = [None] * self.nt

        self.buses_useful_for_storage = [None] * self.nt

        # results available
        self.available_results = [ResultTypes.BusVoltageModule,
                                  ResultTypes.BusVoltageAngle,
                                  ResultTypes.BusActivePower,
                                  ResultTypes.BusReactivePower,

                                  ResultTypes.BranchActivePowerFrom,
                                  ResultTypes.BranchReactivePowerFrom,
                                  ResultTypes.BranchLoading,
                                  ResultTypes.BranchActiveLosses,
                                  ResultTypes.BranchReactiveLosses,
                                  ResultTypes.BranchVoltage,
                                  ResultTypes.BranchAngles,
                                  ResultTypes.SimulationError,

                                  ResultTypes.HvdcLosses,
                                  ResultTypes.HvdcPowerFrom,
                                  ResultTypes.HvdcPowerTo]

    def set_at(self, t, results: PowerFlowResults):
        """
        Set the results at the step t
        @param t: time index
        @param results: PowerFlowResults instance
        """

        self.voltage[t, :] = results.voltage

        self.S[t, :] = results.Sbus

        self.Sf[t, :] = results.Sf
        self.St[t, :] = results.St

        self.Vbranch[t, :] = results.Vbranch

        self.loading[t, :] = results.loading

        self.losses[t, :] = results.losses

        self.flow_direction[t, :] = results.flow_direction

        self.error_values[t] = results.error

        self.converged_values[t] = results.converged

    @staticmethod
    def merge_if(df, arr, ind, cols):
        """

        @param df:
        @param arr:
        @param ind:
        @param cols:
        @return:
        """
        obj = pd.DataFrame(data=arr, index=ind, columns=cols)
        if df is None:
            df = obj
        else:
            df = pd.concat([df, obj], axis=1)

        return df

    def apply_from_island(self, results, b_idx, br_idx, t_index, grid_idx):
        """
        Apply results from another island circuit to the circuit results represented here
        :param results: PowerFlowResults
        :param b_idx: bus original indices
        :param br_idx: branch original indices
        :param t_index:
        :param grid_idx:
        :return:
        """

        # bus results
        if self.voltage.shape == results.voltage.shape:
            self.voltage = results.voltage
            self.S = results.S
        else:
            self.voltage[np.ix_(t_index, b_idx)] = results.voltage
            self.S[np.ix_(t_index, b_idx)] = results.S

        # branch results
        if self.Sf.shape == results.Sf.shape:
            self.Sf = results.Sf
            self.St = results.St

            self.Vbranch = results.Vbranch

            self.loading = results.loading

            self.losses = results.losses

            self.flow_direction = results.flow_direction

            if (results.error_values > self.error_values).any():
                self.error_values += results.error_values

            self.converged_values = self.converged_values * results.converged_values

        else:
            self.Sf[np.ix_(t_index, br_idx)] = results.Sf
            self.St[np.ix_(t_index, br_idx)] = results.St

            self.Vbranch[np.ix_(t_index, br_idx)] = results.Vbranch

            self.loading[np.ix_(t_index, br_idx)] = results.loading

            self.losses[np.ix_(t_index, br_idx)] = results.losses

            self.flow_direction[np.ix_(t_index, br_idx)] = results.flow_direction

            if (results.error_values > self.error_values[t_index]).any():
                self.error_values[t_index] += results.error_values

            self.converged_values[t_index] = self.converged_values[t_index] * results.converged_values

    def get_results_dict(self):
        """
        Returns a dictionary with the results sorted in a dictionary
        :return: dictionary of 2D numpy arrays (probably of complex numbers)
        """
        data = {'Vm': np.abs(self.voltage).tolist(),
                'Va': np.angle(self.voltage).tolist(),
                'P': self.S.real.tolist(),
                'Q': self.S.imag.tolist(),
                'Sf_real': self.Sf.real.tolist(),
                'Sf_imag': self.Sf.imag.tolist(),
                'loading': np.abs(self.loading).tolist(),
                'losses_real': np.real(self.losses).tolist(),
                'losses_imag': np.imag(self.losses).tolist()}
        return data

    def save(self, fname):
        """
        Export as json
        """

        with open(fname, "wb") as output_file:
            json_str = json.dumps(self.get_results_dict())
            output_file.write(json_str)

    def analyze(self):
        """
        Analyze the results
        @return:
        """
        branch_overload_frequency = np.zeros(self.m)
        bus_undervoltage_frequency = np.zeros(self.n)
        bus_overvoltage_frequency = np.zeros(self.n)
        buses_selected_for_storage_frequency = np.zeros(self.n)
        for i in range(self.nt):
            branch_overload_frequency[self.overloads_idx[i]] += 1
            bus_undervoltage_frequency[self.undervoltage_idx[i]] += 1
            bus_overvoltage_frequency[self.overvoltage_idx[i]] += 1
            buses_selected_for_storage_frequency[self.buses_useful_for_storage[i]] += 1

        return branch_overload_frequency, \
                bus_undervoltage_frequency, \
                bus_overvoltage_frequency, \
                buses_selected_for_storage_frequency

    def mdl(self, result_type: ResultTypes) -> "ResultsModel":
        """

        :param result_type:
        :return:
        """

        if result_type == ResultTypes.BusVoltageModule:
            labels = self.bus_names
            data = np.abs(self.voltage)
            y_label = '(p.u.)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusVoltageAngle:
            labels = self.bus_names
            data = np.angle(self.voltage, deg=True)
            y_label = '(Deg)'
            title = 'Bus voltage '

        elif result_type == ResultTypes.BusActivePower:
            labels = self.bus_names
            data = self.S.real
            y_label = '(MW)'
            title = 'Bus active power '

        elif result_type == ResultTypes.BusReactivePower:
            labels = self.bus_names
            data = self.S.imag
            y_label = '(MVAr)'
            title = 'Bus reactive power '

        elif result_type == ResultTypes.BranchPower:
            labels = self.branch_names
            data = self.Sf
            y_label = '(MVA)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchActivePowerFrom:
            labels = self.branch_names
            data = self.Sf.real
            y_label = '(MW)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchReactivePowerFrom:
            labels = self.branch_names
            data = self.Sf.imag
            y_label = '(MVAr)'
            title = 'Branch power '

        elif result_type == ResultTypes.BranchLoading:
            labels = self.branch_names
            data = np.abs(self.loading) * 100
            y_label = '(%)'
            title = 'Branch loading '

        elif result_type == ResultTypes.BranchLosses:
            labels = self.branch_names
            data = self.losses
            y_label = '(MVA)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchActiveLosses:
            labels = self.branch_names
            data = self.losses.real
            y_label = '(MW)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchReactiveLosses:
            labels = self.branch_names
            data = self.losses.imag
            y_label = '(MVAr)'
            title = 'Branch losses'

        elif result_type == ResultTypes.BranchVoltage:
            labels = self.branch_names
            data = np.abs(self.Vbranch)
            y_label = '(p.u.)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BranchAngles:
            labels = self.branch_names
            data = np.angle(self.Vbranch, deg=True)
            y_label = '(deg)'
            title = result_type.value[0]

        elif result_type == ResultTypes.BatteryPower:
            labels = self.branch_names
            data = np.zeros_like(self.losses)
            y_label = '$\Delta$ (MVA)'
            title = 'Battery power'

        elif result_type == ResultTypes.SimulationError:
            data = self.error_values.reshape(-1, 1)
            y_label = 'p.u.'
            labels = ['Error']
            title = 'Error'

        elif result_type == ResultTypes.HvdcLosses:
            labels = self.hvdc_names
            data = self.hvdc_losses
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerFrom:
            labels = self.hvdc_names
            data = self.hvdc_Pf
            y_label = '(MW)'
            title = result_type.value

        elif result_type == ResultTypes.HvdcPowerTo:
            labels = self.hvdc_names
            data = self.hvdc_Pt
            y_label = '(MW)'
            title = result_type.value

        else:
            raise Exception('Result type not understood:' + str(result_type))

        if self.time is not None:
            index = self.time
        else:
            index = list(range(data.shape[0]))

        # assemble model
        mdl = ResultsModel(data=data, index=index, columns=labels, title=title, ylabel=y_label, units=y_label)
        return mdl


def kmeans_case_sampling(X, n_points=10):
    """
    K-Means clustering
    :param X: injections matrix (time, bus)
    :param n_points: number of clusters
    :return: indices of the closest to the cluster centers, deviation of the closest representatives
    """

    # declare the model
    model = KMeans(n_clusters=n_points)

    # model fitting
    model.fit(X)

    centers = model.cluster_centers_
    labels = model.labels_

    # get the closest indices to the cluster centers
    closest_idx = np.zeros(n_points, dtype=int)
    closest_prob = np.zeros(n_points, dtype=float)
    nt = X.shape[0]

    unique_labels, counts = np.unique(labels, return_counts=True)
    probabilities = counts.astype(float) / float(nt)

    prob_dict = {u: p for u, p in zip(unique_labels, probabilities)}
    for i in range(n_points):
        deviations = np.sum(np.power(X - centers[i, :], 2.0), axis=1)
        idx = deviations.argmin()
        closest_idx[i] = idx

    # sort the indices
    closest_idx = np.sort(closest_idx)

    # compute the probabilities of each index (sorted already)
    for i, idx in enumerate(closest_idx):
        lbl = model.predict(X[idx, :].reshape(1, -1))[0]
        prob = prob_dict[lbl]
        closest_prob[i] = prob

    return closest_idx, closest_prob


class TimeSeriesClustering(QThread):
    progress_signal = Signal(float)
    progress_text = Signal(str)
    done_signal = Signal()
    name = 'Time Series Clustering'

    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_time_series_results=None,
                 start_=0, end_=None, use_clustering=False, cluster_number=10):
        """
        TimeSeries constructor
        @param grid: MultiCircuit instance
        @param options: PowerFlowOptions instance
        """
        QThread.__init__(self)

        # reference the grid directly
        self.grid = grid

        self.options = options

        self.opf_time_series_results = opf_time_series_results

        self.results = None

        self.start_ = start_

        self.end_ = end_

        self.use_clustering = use_clustering

        self.cluster_number = cluster_number

        self.elapsed = 0

        self.logger = Logger()

        self.returned_results = list()

        self.pool = None

        self._mt_i = 0
        self._mt_n = 1

        self.__cancel__ = False

    def get_steps(self):
        """
        Get time steps list of strings
        """
        return [l.strftime('%d-%m-%Y %H:%M') for l in pd.to_datetime(self.grid.time_profile[self.start_: self.end_])]

    def run_single_thread(self, time_indices) -> TimeSeriesClusteringResults:
        """
        Run single thread time series
        :param time_indices: array of time indices to consider
        :return: TimeSeriesResults instance
        """

        # compile the multi-circuit
        time_circuit = compile_time_circuit(circuit=self.grid,
                                            apply_temperature=False,
                                            branch_tolerance_mode=BranchImpedanceMode.Specified,
                                            opf_results=self.opf_time_series_results)

        # do the topological computation
        time_islands = time_circuit.split_into_islands(ignore_single_node_islands=self.options.ignore_single_node_islands)

        # initialize the grid time series results we will append the island results with another function
        time_series_results = TimeSeriesClusteringResults(n=time_circuit.nbus,
                                                          m=time_circuit.nbr,
                                                          n_tr=time_circuit.ntr,
                                                          n_hvdc=time_circuit.nhvdc,
                                                          bus_names=time_circuit.bus_names,
                                                          branch_names=time_circuit.branch_names,
                                                          transformer_names=time_circuit.tr_names,
                                                          hvdc_names=time_circuit.hvdc_names,
                                                          bus_types=time_circuit.bus_types,
                                                          time_array=self.grid.time_profile[time_indices])

        time_series_results.bus_types = time_circuit.bus_types

        # For every island, run the time series
        for island_index, calculation_input in enumerate(time_islands):

            # fill in Vbus, Sbus Ibus
            # calculation_input.consolidate()

            # Are we dispatching storage? if so, generate a dictionary of battery -> bus index
            # to be able to set the batteries values into the vector S
            batteries = list()
            batteries_bus_idx = list()
            if self.options.dispatch_storage:
                for k, bus in enumerate(self.grid.buses):
                    for battery in bus.batteries:
                        battery.reset()  # reset the calculation values
                        batteries.append(battery)
                        batteries_bus_idx.append(k)

            self.progress_text.emit('Time series at circuit ' + str(island_index) + '...')

            # find the original indices
            bus_original_idx = calculation_input.original_bus_idx
            branch_original_idx = calculation_input.original_branch_idx

            # declare a results object for the partition
            results = TimeSeriesClusteringResults(n=calculation_input.nbus,
                                                  m=calculation_input.nbr,
                                                  n_tr=calculation_input.ntr,
                                                  n_hvdc=calculation_input.nhvdc,
                                                  bus_names=calculation_input.bus_names,
                                                  branch_names=calculation_input.branch_names,
                                                  transformer_names=calculation_input.tr_names,
                                                  hvdc_names=calculation_input.hvdc_names,
                                                  bus_types=time_circuit.bus_types,
                                                  time_array=self.grid.time_profile[time_indices])

            self.progress_signal.emit(0.0)

            # default value in case of single-valued profile
            dt = 1.0

            # traverse the time profiles of the partition and simulate each time step
            for it, t in enumerate(time_indices):

                # set the power values
                # if the storage dispatch option is active, the batteries power is not included
                # therefore, it shall be included after processing
                V = calculation_input.Vbus[:, it]
                # Ysh = calculation_input.Yshunt_from_devices[:, it]
                I = calculation_input.Ibus[:, it]
                S = calculation_input.Sbus[:, it]
                branch_rates = calculation_input.Rates[:, it]

                # add the controlled storage power if we are controlling the storage devices
                if self.options.dispatch_storage:

                    if (it+1) < len(calculation_input.original_time_idx):
                        # compute the time delta: the time values come in nanoseconds
                        dt = (calculation_input.time_array[it + 1]
                              - calculation_input.time_array[it]).value * 1e-9 / 3600.0

                    for k, battery in enumerate(batteries):

                        power = battery.get_processed_at(it, dt=dt, store_values=True)

                        bus_idx = batteries_bus_idx[k]

                        S[bus_idx] += power / calculation_input.Sbase

                # run power flow at the circuit
                res = single_island_pf(circuit=calculation_input,
                                       Vbus=V,
                                       Sbus=S,
                                       Ibus=I,
                                       branch_rates=branch_rates,
                                       options=self.options,
                                       logger=self.logger)

                # Recycle voltage solution
                # last_voltage = res.voltage

                # store circuit results at the time index 'it'
                results.set_at(it, res)

                progress = ((t - self.start_ + 1) / (self.end_ - self.start_)) * 100
                self.progress_signal.emit(progress)
                self.progress_text.emit('Simulating island ' + str(island_index)
                                        + ' at ' + str(self.grid.time_profile[t]))

                if self.__cancel__:
                    # merge the circuit's results
                    time_series_results.apply_from_island(results,
                                                          bus_original_idx,
                                                          branch_original_idx,
                                                          time_indices,
                                                          'TS')
                    # abort by returning at this point
                    return time_series_results

            # merge the circuit's results
            time_series_results.apply_from_island(results,
                                                  bus_original_idx,
                                                  branch_original_idx,
                                                  time_indices,
                                                  'TS')

        # set the HVDC results here since the HVDC is not a branch in this modality
        time_series_results.hvdc_Pf = -time_circuit.hvdc_Pf.T
        time_series_results.hvdc_Pt = -time_circuit.hvdc_Pt.T
        time_series_results.hvdc_loading = time_circuit.hvdc_loading.T
        time_series_results.hvdc_losses = time_circuit.hvdc_losses.T

        return time_series_results

    def run(self):
        """
        Run the time series simulation
        @return:
        """

        a = time.time()

        if self.end_ is None:
            self.end_ = len(self.grid.time_profile)
        time_indices = np.arange(self.start_, self.end_)

        # compile the multi-circuit
        time_circuit = compile_time_circuit(circuit=self.grid,
                                            apply_temperature=False,
                                            branch_tolerance_mode=BranchImpedanceMode.Specified,
                                            opf_results=self.opf_time_series_results)

        self.progress_text.emit('Clustering...')
        X = time_circuit.Sbus
        X = X[:, time_indices].real.T
        time_idx, closest_prob = kmeans_case_sampling(X, n_points=self.cluster_number)

        self.results = self.run_single_thread(time_indices=time_idx)

        self.elapsed = time.time() - a

        # send the finnish signal
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Done!')
        self.done_signal.emit()

    def cancel(self):
        """
        Cancel the simulation
        """
        self.__cancel__ = True
        if self.pool is not None:
            self.pool.terminate()
        self.progress_signal.emit(0.0)
        self.progress_text.emit('Cancelled!')
        self.done_signal.emit()
