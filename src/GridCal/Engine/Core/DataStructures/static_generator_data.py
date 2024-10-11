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
import scipy.sparse as sp
import GridCal.Engine.Core.topology as tp


class StaticGeneratorData:

    def __init__(self, nstagen, nbus, ntime=1):
        """

        :param nstagen:
        :param nbus:
        """
        self.nstagen = nstagen
        self.ntime = ntime

        self.names = np.empty(nstagen, dtype=object)

        self.active = np.zeros((nstagen, ntime), dtype=bool)
        self.S = np.zeros((nstagen, ntime), dtype=complex)

        self.C_bus_static_generator = sp.lil_matrix((nbus, nstagen), dtype=int)

    def slice(self, elm_idx, bus_idx, time_idx=None):
        """

        :param elm_idx:
        :param bus_idx:
        :param time_idx: 
        :return:
        """
        if time_idx is None:
            tidx = elm_idx
        else:
            tidx = np.ix_(elm_idx, time_idx)

        data = StaticGeneratorData(nstagen=len(elm_idx), nbus=len(bus_idx))
        data.names = self.names[elm_idx]

        data.active = self.active[tidx]
        data.S = self.S[tidx]

        data.C_bus_static_generator = self.C_bus_static_generator[np.ix_(bus_idx, elm_idx)]

        return data

    def get_island(self, bus_idx, t_idx=0):
        if self.nstagen:
            return tp.get_elements_of_the_island(self.C_bus_static_generator.T, bus_idx, active=self.active[t_idx])
        else:
            return np.zeros(0, dtype=int)

    def get_injections_per_bus(self):
        return self.C_bus_static_generator * (self.S * self.active)

    def __len__(self):
        return self.nstagen
