# GridCal
# Copyright (C) 2022 Santiago Peñate Vera
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
import numpy as np
from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Simulations.PowerFlow.power_flow_options import PowerFlowOptions
from GridCal.Engine.Simulations.PowerFlow.power_flow_worker import multi_island_pf
from GridCal.Engine.Simulations.PowerFlow.power_flow_results import PowerFlowResults
# from GridCal.Engine.Simulations.OPF.opf_results import OptimalPowerFlowResults
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.Simulations.driver_types import SimulationTypes
from GridCal.Engine.Simulations.driver_template import DriverTemplate
from GridCal.Engine.Core.Compilers.circuit_to_bentayga import BENTAYGA_AVAILABLE, bentayga_pf, translate_bentayga_pf_results
from GridCal.Engine.Core.Compilers.circuit_to_newton_pa import NEWTON_PA_AVAILABLE, newton_pa_pf, translate_newton_pa_pf_results
from GridCal.Engine.Core.Compilers.circuit_to_alliander_pgm import ALLIANDER_PGM_AVAILABLE, alliander_pgm_pf
import GridCal.Engine.basic_structures as bs


class PowerFlowDriver(DriverTemplate):
    name = 'Power Flow'
    tpe = SimulationTypes.PowerFlow_run

    """
    Power flow wrapper to use with Qt
    """
    def __init__(self, grid: MultiCircuit, options: PowerFlowOptions, opf_results: "OptimalPowerFlowResults" = None,
                 engine: bs.EngineType = bs.EngineType.GridCal):
        """
        PowerFlowDriver class constructor
        :param grid: MultiCircuit instance
        :param options: PowerFlowOptions instance
        :param opf_results: OptimalPowerFlowResults instance
        """

        DriverTemplate.__init__(self, grid=grid, engine=engine)

        # Options to use
        self.options = options

        self.opf_results = opf_results

        self.results = PowerFlowResults(n=0, m=0, n_tr=0, n_hvdc=0,
                                        bus_names=(), branch_names=(), transformer_names=(),
                                        hvdc_names=(), bus_types=())

        self.logger = Logger()

        self.convergence_reports = list()

        self.__cancel__ = False

    def get_steps(self):
        """

        :return:
        """
        return list()

    def run(self):
        """
        Pack run_pf for the QThread
        :return:
        """
        if self.engine == bs.EngineType.NewtonPA and not NEWTON_PA_AVAILABLE:
            self.engine = bs.EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == bs.EngineType.Bentayga and not BENTAYGA_AVAILABLE:
            self.engine = bs.EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == bs.EngineType.AllianderPGM and not ALLIANDER_PGM_AVAILABLE:
            self.engine = bs.EngineType.GridCal
            self.logger.add_warning('Failed back to GridCal')

        if self.engine == bs.EngineType.GridCal:
            self.results = multi_island_pf(multi_circuit=self.grid,
                                           options=self.options,
                                           opf_results=self.opf_results,
                                           logger=self.logger)
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == bs.EngineType.NewtonPA:

            res = newton_pa_pf(circuit=self.grid, opt=self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_tr=self.grid.get_transformers2w_number(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            bus_names=res.bus_names,
                                            branch_names=res.branch_names,
                                            transformer_names=[],
                                            hvdc_names=res.hvdc_names,
                                            bus_types=res.bus_types)

            self.results = translate_newton_pa_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == bs.EngineType.Bentayga:

            res = bentayga_pf(self.grid, self.options, time_series=False)

            self.results = PowerFlowResults(n=self.grid.get_bus_number(),
                                            m=self.grid.get_branch_number_wo_hvdc(),
                                            n_tr=self.grid.get_transformers2w_number(),
                                            n_hvdc=self.grid.get_hvdc_number(),
                                            bus_names=res.names,
                                            branch_names=res.names,
                                            transformer_names=[],
                                            hvdc_names=res.hvdc_names,
                                            bus_types=res.bus_types)

            self.results = translate_bentayga_pf_results(self.grid, res)
            self.results.area_names = [a.name for a in self.grid.areas]
            self.convergence_reports = self.results.convergence_reports

        elif self.engine == bs.EngineType.AllianderPGM:

            self.results = alliander_pgm_pf(self.grid, self.options, logger=self.logger)
            self.results.area_names = [a.name for a in self.grid.areas]

        else:
            raise Exception('Engine ' + self.engine.value + ' not implemented for ' + self.name)

        # fill F, T, Areas, etc...
        self.results.fill_circuit_info(self.grid)
