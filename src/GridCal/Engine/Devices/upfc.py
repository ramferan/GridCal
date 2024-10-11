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

import pandas as pd
import numpy as np
from matplotlib import pyplot as plt

from GridCal.Engine.Devices.bus import Bus
from GridCal.Engine.Devices.enumerations import BranchType, ConverterControlType, BuildStatus

from GridCal.Engine.Devices.editable_device import EditableDevice, DeviceType, GCProp


class UPFC(EditableDevice):

    def __init__(self, bus_from: Bus = None, bus_to: Bus = None, name='UPFC', code='', idtag=None, active=True,
                 rs=0.0, xs=0.00001, rp=0.0, xp=0.0, vp=1.0, Pset = 0.0, Qset=0.0, rate=9999,
                 mttf=0, mttr=0, cost=100, cost_prof=None, rate_prof=None, active_prof=None, contingency_factor=1.0,
                 contingency_enabled=True, monitor_loading=True, contingency_factor_prof=None,
                 rs0=0.0, xs0=0.00001, rp0=0.0, xp0=0.0,
                 rs2=0.0, xs2=0.00001, rp2=0.0, xp2=0.0,
                 capex=0, opex=0, build_status: BuildStatus = BuildStatus.Commissioned):
        """
        Unified Power Flow Converter (UPFC)
        :param bus_from:
        :param bus_to:
        :param name:
        :param idtag:
        :param active:
        :param rs: series resistance (p.u.)
        :param xs: series reactance (p.u.)
        :param rp: shunt resistance (p.u.)
        :param xp: shunt reactance (p.u.)
        :param vp: shunt voltage set point (p.u.)
        :param rate: Power rating (MVA)
        :param Pset: Power set point (MW)
        :param mttf:
        :param mttr:
        :param cost:
        :param cost_prof:
        :param rate_prof:
        :param active_prof:
        """

        EditableDevice.__init__(self,
                                name=name,
                                idtag=idtag,
                                active=active,
                                code=code,
                                device_type=DeviceType.UpfcDevice,
                                editable_headers={'name': GCProp('', str, 'Name of the branch.'),
                                                  'idtag': GCProp('', str, 'Unique ID'),
                                                  'code': GCProp('', str, 'Secondary ID'),
                                                  'bus_from': GCProp('', DeviceType.BusDevice,
                                                                     'Name of the bus at the "from" side of the branch.'),
                                                  'bus_to': GCProp('', DeviceType.BusDevice,
                                                                   'Name of the bus at the "to" side of the branch.'),
                                                  'active': GCProp('', bool, 'Is the branch active?'),
                                                  'rate': GCProp('MVA', float, 'Thermal rating power of the branch.'),

                                                  'contingency_factor': GCProp('p.u.', float,
                                                                               'Rating multiplier for contingencies.'),
                                                  'contingency_enabled': GCProp('', bool,
                                                                                'Consider this UPFC for contingencies.'),
                                                  'monitor_loading': GCProp('', bool,
                                                                            'Monitor this device loading for optimization, NTC or contingency studies.'),
                                                  'mttf': GCProp('h', float, 'Mean time to failure, '
                                                                 'used in reliability studies.'),
                                                  'mttr': GCProp('h', float, 'Mean time to recovery, '
                                                                 'used in reliability studies.'),

                                                  'Rs': GCProp('p.u.', float, 'Series positive sequence resistance.'),
                                                  'Xs': GCProp('p.u.', float, 'Series positive sequence reactance.'),
                                                  'Rsh': GCProp('p.u.', float, 'Shunt positive sequence resistance.'),
                                                  'Xsh': GCProp('p.u.', float, 'Shunt positive sequence resistance.'),

                                                  'Rs0': GCProp('p.u.', float, 'Series zero sequence resistance.'),
                                                  'Xs0': GCProp('p.u.', float, 'Series zero sequence reactance.'),
                                                  'Rsh0': GCProp('p.u.', float, 'Shunt zero sequence resistance.'),
                                                  'Xsh0': GCProp('p.u.', float, 'Shunt zero sequence resistance.'),

                                                  'Rs2': GCProp('p.u.', float, 'Series negative sequence resistance.'),
                                                  'Xs2': GCProp('p.u.', float, 'Series negative sequence reactance.'),
                                                  'Rsh2': GCProp('p.u.', float, 'Shunt negative sequence resistance.'),
                                                  'Xsh2': GCProp('p.u.', float, 'Shunt negative sequence resistance.'),

                                                  'Vsh': GCProp('p.u.', float, 'Shunt voltage set point.'),
                                                  'Pfset': GCProp('MW', float, 'Active power set point.'),
                                                  'Qfset': GCProp('MVAr', float, 'Active power set point.'),
                                                  'Cost': GCProp('e/MWh', float, 'Cost of overloads. Used in OPF.'),
                                                  'capex': GCProp('e/MW', float,
                                                                  'Cost of investment. Used in expansion planning.'),
                                                  'opex': GCProp('e/MWh', float,
                                                                 'Cost of operation. Used in expansion planning.'),
                                                  'build_status': GCProp('', BuildStatus,
                                                                         'Branch build status. Used in expansion planning.'),
                                                  },
                                non_editable_attributes=['bus_from', 'bus_to', 'idtag'],
                                properties_with_profile={'active': 'active_prof',
                                                         'rate': 'rate_prof',
                                                         'contingency_factor': 'contingency_factor_prof',
                                                         'Cost': 'Cost_prof'})

        self.bus_from = bus_from
        self.bus_to = bus_to

        # List of measurements
        self.measurements = list()

        # total impedance and admittance in p.u.
        self.Rs = rs
        self.Xs = xs
        self.Rsh = rp
        self.Xsh = xp

        self.Rs0 = rs0
        self.Xs0 = xs0
        self.Rsh0 = rp0
        self.Xsh0 = xp0

        self.Rs2 = rs2
        self.Xs2 = xs2
        self.Rsh2 = rp2
        self.Xsh2 = xp2

        self.Vsh = vp
        self.Pfset = Pset
        self.Qfset = Qset

        self.Cost = cost
        self.Cost_prof = cost_prof

        self.capex = capex

        self.opex = opex

        self.build_status = build_status

        self.mttf = mttf
        self.mttr = mttr

        self.active = active
        self.active_prof = active_prof

        # branch rating in MVA
        self.rate = rate
        self.contingency_factor = contingency_factor
        self.contingency_enabled: bool = contingency_enabled
        self.monitor_loading: bool = monitor_loading
        self.rate_prof = rate_prof
        self.contingency_factor_prof = contingency_factor_prof

        # branch type: Line, Transformer, etc...
        self.branch_type = BranchType.UPFC

    def get_ysh1(self):
        return 1.0 / complex(self.Rsh, self.Xsh)

    def get_ysh0(self):
        return 1.0 / complex(self.Rsh0, self.Xsh0)

    def get_ysh2(self):
        return 1.0 / complex(self.Rsh2, self.Xsh2)

    def get_max_bus_nominal_voltage(self):
        return max(self.bus_from.Vnom, self.bus_to.Vnom)

    def get_min_bus_nominal_voltage(self):
        return min(self.bus_from.Vnom, self.bus_to.Vnom)

    def change_base(self, Sbase_old, Sbase_new):
        b = Sbase_new / Sbase_old

        self.Rs *= b
        self.Xs *= b
        self.Rsh *= b
        self.Xs *= b

    def get_properties_dict(self, version=3):
        """
        Get json dictionary
        :return:
        """
        if version == 2:
            return {'id': self.idtag,
                    'type': 'upfc',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,
                    'rate': self.rate,
                    'rl': 0.0,
                    'xl': 0.0,
                    'bl': 0.0,
                    'rs': self.Rs,
                    'xs': self.Xs,
                    'rsh': self.Rsh,
                    'xsh': self.Xsh,
                    'vsh': self.Vsh,
                    'Pfset': self.Pfset,
                    'Qfset': self.Qfset
                    }
        elif version == 3:
            return {'id': self.idtag,
                    'type': 'upfc',
                    'phases': 'ps',
                    'name': self.name,
                    'name_code': self.code,
                    'bus_from': self.bus_from.idtag,
                    'bus_to': self.bus_to.idtag,
                    'active': self.active,
                    'rate': self.rate,
                    'contingency_factor1': self.contingency_factor,
                    'contingency_factor2': self.contingency_factor,
                    'contingency_factor3': self.contingency_factor,
                    'rl': 0.0,
                    'xl': 0.0,
                    'bl': 0.0,
                    'rs': self.Rs,
                    'xs': self.Xs,
                    'rsh': self.Rsh,
                    'xsh': self.Xsh,
                    'vsh': self.Vsh,
                    'Pfset': self.Pfset,
                    'Qfset': self.Qfset,

                    'overload_cost': self.Cost,
                    'capex': self.capex,
                    'opex': self.opex,
                    'build_status': str(self.build_status.value).lower(),
                    }
        else:
            return dict()

    def get_profiles_dict(self, version=3):
        """

        :return:
        """
        if self.active_prof is not None:
            active_prof = self.active_prof.tolist()
            rate_prof = self.rate_prof.tolist()
        else:
            active_prof = list()
            rate_prof = list()

        return {'id': self.idtag,
                'active': active_prof,
                'rate': rate_prof}

    def get_units_dict(self, version=3):
        """
        Get units of the values
        """
        return {'rate': 'MW',
                'r': 'p.u.',
                'x': 'p.u.',
                'b': 'p.u.',
                'g': 'p.u.'}

    def get_coordinates(self):
        """
        Get the branch defining coordinates
        """
        return [self.bus_from.get_coordinates(), self.bus_to.get_coordinates()]

    def plot_profiles(self, time_series=None, my_index=0, show_fig=True):
        """
        Plot the time series results of this object
        :param time_series: TimeSeries Instance
        :param my_index: index of this object in the simulation
        :param show_fig: Show the figure?
        """

        if time_series is not None:
            fig = plt.figure(figsize=(12, 8))

            ax_1 = fig.add_subplot(211)
            ax_2 = fig.add_subplot(212, sharex=ax_1)

            x = time_series.results.time

            # loading
            y = time_series.results.loading.real * 100.0
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_1.set_title('Loading', fontsize=14)
            ax_1.set_ylabel('Loading [%]', fontsize=11)
            df.plot(ax=ax_1)

            # losses
            y = np.abs(time_series.results.losses)
            df = pd.DataFrame(data=y[:, my_index], index=x, columns=[self.name])
            ax_2.set_title('Losses', fontsize=14)
            ax_2.set_ylabel('Losses [MVA]', fontsize=11)
            df.plot(ax=ax_2)

            plt.legend()
            fig.suptitle(self.name, fontsize=20)

        if show_fig:
            plt.show()
