from GridCal.Engine.basic_structures import Logger
from GridCal.Engine.Core.multi_circuit import MultiCircuit
from GridCal.Engine.basic_structures import BranchImpedanceMode
from GridCal.Engine.basic_structures import BusMode
from GridCal.Engine.Devices.enumerations import ConverterControlType, TransformerControlType
from GridCal.Engine.Core.DataStructures import *


def get_bus_data(circuit: MultiCircuit, time_series=False, ntime=1, use_stored_guess=False):
    """

    :param circuit:
    :param time_series:
    :param ntime:
    :param use_stored_guess:
    :return:
    """
    bus_data = BusData(nbus=len(circuit.buses), ntime=ntime)

    areas_dict = {elm: k for k, elm in enumerate(circuit.areas)}

    for i, bus in enumerate(circuit.buses):

        # bus parameters
        bus_data.names[i] = bus.name
        bus_data.Vmin[i] = bus.Vmin
        bus_data.Vmax[i] = bus.Vmax
        bus_data.Vbus[i] = bus.get_voltage_guess(None, use_stored_guess=use_stored_guess)

        bus_data.angle_min[i] = bus.angle_min
        bus_data.angle_max[i] = bus.angle_max

        bus_data.bus_types[i] = bus.determine_bus_type().value

        bus_data.areas[i] = areas_dict.get(bus.area, 0)

        # if bus.area in areas_dict.keys():
        #     bus_data.areas[i] = areas_dict[bus.area]
        # else:
        #     bus_data.areas[i] = 0

        if time_series:
            bus_data.active[i, :] = bus.active_prof
            bus_data.bus_types_prof[i, :] = bus.determine_bus_type_prof()
        else:
            bus_data.active[i] = bus.active

    return bus_data


def get_load_data(circuit: MultiCircuit, bus_dict, opf_results=None, time_series=False, opf=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param opf_results:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """

    devices = circuit.get_loads()

    if opf:
        data = LoadOpfData(nload=len(devices), nbus=len(circuit.buses), ntime=ntime)
    else:
        data = LoadData(nload=len(devices), nbus=len(circuit.buses), ntime=ntime)

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name

        if time_series:
            data.S[k, :] = elm.P_prof + 1j * elm.Q_prof
            data.I[k, :] = elm.Ir_prof + 1j * elm.Ii_prof
            data.Y[k, :] = elm.G_prof + 1j * elm.B_prof
            data.active[k] = elm.active_prof

            if opf:
                data.load_cost[k, :] = elm.Cost_prof

            if opf_results is not None:
                data.S[k, :] -= opf_results.load_shedding[:, k]

        else:
            data.S[k] = complex(elm.P, elm.Q)
            data.I[k] = complex(elm.Ir, elm.Ii)
            data.Y[k] = complex(elm.G, elm.B)
            data.active[k] = elm.active

            if opf:
                data.load_cost[k] = elm.Cost

            if opf_results is not None:
                data.S[k] -= opf_results.load_shedding[k]

        data.C_bus_load[i, k] = 1

    return data


def get_static_generator_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param time_series:
    :return:
    """
    devices = circuit.get_static_generators()

    data = StaticGeneratorData(nstagen=len(devices), nbus=len(circuit.buses), ntime=ntime)

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name

        if time_series:
            data.active[k, :] = elm.active_prof
            data.S[k, :] = elm.P_prof + 1j * elm.Q_prof
        else:
            data.active[k] = elm.active
            data.S[k] = complex(elm.P, elm.Q)

        data.C_bus_static_generator[i, k] = 1

    return data


def get_shunt_data(circuit: MultiCircuit, bus_dict, Vbus, logger: Logger, time_series=False, ntime=1, use_stored_guess=False):
    """

    :param circuit:
    :param bus_dict:
    :param time_series:
    :return:
    """
    devices = circuit.get_shunts()

    data = ShuntData(nshunt=len(devices), nbus=len(circuit.buses), ntime=ntime)

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.controlled[k] = elm.is_controlled
        data.b_min[k] = elm.Bmin
        data.b_max[k] = elm.Bmax

        if time_series:
            data.active[k, :] = elm.active_prof
            data.admittance[k, :] = elm.G_prof + 1j * elm.B_prof
        else:
            data.active[k] = elm.active
            data.admittance[k] = complex(elm.G, elm.B)

        if not use_stored_guess:
            if Vbus[i, 0].real == 1.0:
                Vbus[i, :] = complex(elm.Vset, 0)
            elif elm.Vset != Vbus[i, 0]:
                logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i, 0])

        data.C_bus_shunt[i, k] = 1

    return data


def get_generator_data(circuit: MultiCircuit, bus_dict, Vbus, logger: Logger,
                       opf_results: "OptimalPowerFlowResults" = None, time_series=False, opf=False, ntime=1,
                       use_stored_guess=False):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    devices = circuit.get_generators()

    if opf:
        data = GeneratorOpfData(ngen=len(devices), nbus=len(circuit.buses), ntime=ntime)
    else:
        data = GeneratorData(ngen=len(devices), nbus=len(circuit.buses), ntime=ntime)

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.qmin[k] = elm.Qmin
        data.qmax[k] = elm.Qmax
        data.controllable[k] = elm.is_controlled
        data.installed_p[k] = elm.Snom

        # r0, r1, r2, x0, x1, x2
        data.r0[k] = elm.R0
        data.r1[k] = elm.R1
        data.r2[k] = elm.R2
        data.x0[k] = elm.X0
        data.x1[k] = elm.X1
        data.x2[k] = elm.X2

        if time_series:
            data.p[k] = elm.P_prof
            data.active[k] = elm.active_prof
            data.pf[k] = elm.Pf_prof
            data.v[k] = elm.Vset_prof

            if opf:
                data.generator_dispatchable[k] = elm.enabled_dispatch
                data.generator_pmax[k] = elm.Pmax
                data.generator_pmin[k] = elm.Pmin
                data.generator_cost[k] = elm.Cost_prof
                data.generator_cost[k] = elm.Cost_prof

            if opf_results is not None:
                data.p[k, :] = opf_results.generator_power[:, k] - opf_results.generator_shedding[:, k]

        else:
            data.p[k] = elm.P
            data.active[k] = elm.active
            data.pf[k] = elm.Pf
            data.v[k] = elm.Vset

            if opf:
                data.generator_dispatchable[k] = elm.enabled_dispatch
                data.generator_pmax[k] = elm.Pmax
                data.generator_pmin[k] = elm.Pmin
                data.generator_cost[k] = elm.Cost

            if opf_results is not None:
                data.p[k] = opf_results.generator_power[k] - opf_results.generator_shedding[k]

        data.C_bus_gen[i, k] = 1

        if not use_stored_guess:
            if Vbus[i, 0].real == 1.0:
                Vbus[i, :] = complex(elm.Vset, 0)
            elif elm.Vset != Vbus[i, 0]:
                logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i, 0])

    return data


def get_battery_data(circuit: MultiCircuit, bus_dict, Vbus, logger: Logger,
                     opf_results=None, time_series=False, opf=False, ntime=1,
                     use_stored_guess=False):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus:
    :param logger:
    :param opf_results:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    devices = circuit.get_batteries()

    if opf:
        data = BatteryOpfData(nbatt=len(devices), nbus=len(circuit.buses), ntime=ntime)
    else:
        data = BatteryData(nbatt=len(devices), nbus=len(circuit.buses), ntime=ntime)

    for k, elm in enumerate(devices):

        i = bus_dict[elm.bus]

        data.names[k] = elm.name
        data.qmin[k] = elm.Qmin
        data.qmax[k] = elm.Qmax

        data.controllable[k] = elm.is_controlled
        data.installed_p[k] = elm.Snom

        # r0, r1, r2, x0, x1, x2
        data.r0[k] = elm.R0
        data.r1[k] = elm.R1
        data.r2[k] = elm.R2
        data.x0[k] = elm.X0
        data.x1[k] = elm.X1
        data.x2[k] = elm.X2

        if time_series:
            data.p[k, :] = elm.P_prof
            data.active[k, :] = elm.active_prof
            data.pf[k, :] = elm.Pf_prof
            data.v[k, :] = elm.Vset_prof

            if opf:
                data.battery_dispatchable[k] = elm.enabled_dispatch
                data.battery_pmax[k] = elm.Pmax
                data.battery_pmin[k] = elm.Pmin
                data.battery_enom[k] = elm.Enom
                data.battery_min_soc[k] = elm.min_soc
                data.battery_max_soc[k] = elm.max_soc
                data.battery_soc_0[k] = elm.soc_0
                data.battery_discharge_efficiency[k] = elm.discharge_efficiency
                data.battery_charge_efficiency[k] = elm.charge_efficiency
                data.battery_cost[k] = elm.Cost_prof

            if opf_results is not None:
                data.p[k, :] = opf_results.battery_power[:, k]

        else:
            data.p[k] = elm.P
            data.active[k] = elm.active
            data.pf[k] = elm.Pf
            data.v[k] = elm.Vset

            if opf:
                data.battery_dispatchable[k] = elm.enabled_dispatch
                data.battery_pmax[k] = elm.Pmax
                data.battery_pmin[k] = elm.Pmin
                data.battery_enom[k] = elm.Enom
                data.battery_min_soc[k] = elm.min_soc
                data.battery_max_soc[k] = elm.max_soc
                data.battery_soc_0[k] = elm.soc_0
                data.battery_discharge_efficiency[k] = elm.discharge_efficiency
                data.battery_charge_efficiency[k] = elm.charge_efficiency
                data.battery_cost[k] = elm.Cost

            if opf_results is not None:
                data.p[k] = opf_results.battery_power[k]

        data.C_bus_batt[i, k] = 1

        if not use_stored_guess:
            if Vbus[i, 0].real == 1.0:
                Vbus[i, :] = complex(elm.Vset, 0)
            elif elm.Vset != Vbus[i, 0]:
                logger.add_error('Different set points', elm.bus.name, elm.Vset, Vbus[i, 0])

    return data


def get_line_data(circuit: MultiCircuit, bus_dict,
                  apply_temperature, branch_tolerance_mode: BranchImpedanceMode, time_series=False, ntime=1):

    """

    :param circuit:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :return:
    """

    data = LinesData(nline=len(circuit.lines),
                     nbus=len(circuit.buses),
                     ntime=ntime)

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[i] = elm.name
        data.codes[i] = elm.code

        if time_series:
            data.active[i, :] = elm.active_prof
        else:
            data.active[i] = elm.active

        if apply_temperature:
            data.R[i] = elm.R_corrected
        else:
            data.R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[i] *= (1 + elm.tolerance / 100.0)

        data.X[i] = elm.X
        data.B[i] = elm.B
        data.C_line_bus[i, f] = 1
        data.C_line_bus[i, t] = 1

    return data


def get_transformer_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = TransformerData(ntr=len(circuit.transformers2w),
                           nbus=len(circuit.buses),
                           ntime=ntime)

    # 2-winding transformers
    for i, elm in enumerate(circuit.transformers2w):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.names[i] = elm.name
        data.codes[i] = elm.code

        if time_series:
            data.active[i, :] = elm.active_prof
        else:
            data.active[i] = elm.active

        # impedance
        data.R[i] = elm.R
        data.X[i] = elm.X
        data.G[i] = elm.G
        data.B[i] = elm.B

        data.C_tr_bus[i, f] = 1
        data.C_tr_bus[i, t] = -1

        # tap changer
        data.tap_mod[i] = elm.tap_module
        data.tap_ang[i] = elm.angle
        data.is_bus_to_regulated[i] = elm.bus_to_regulated
        data.tap_position[i] = elm.tap_changer.tap
        data.min_tap[i] = elm.tap_changer.min_tap
        data.max_tap[i] = elm.tap_changer.max_tap
        data.tap_inc_reg_up[i] = elm.tap_changer.inc_reg_up
        data.tap_inc_reg_down[i] = elm.tap_changer.inc_reg_down
        data.vset[i] = elm.vset
        data.control_mode[i] = elm.control_mode

        data.bus_to_regulated_idx[i] = t if elm.bus_to_regulated else f

        # virtual taps for transformers where the connection voltage is off
        data.tap_f[i], data.tap_t[i] = elm.get_virtual_taps()

    return data


def get_vsc_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = VscData(nvsc=len(circuit.vsc_devices), nbus=len(circuit.buses), ntime=ntime)

    # VSC
    for i, elm in enumerate(circuit.vsc_devices):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        if time_series:
            data.active[i, :] = elm.active_prof
        else:
            data.active[i] = elm.active

        # vsc values
        data.names[i] = elm.name
        data.R1[i] = elm.R1
        data.X1[i] = elm.X1
        data.G0[i] = elm.G0sw
        data.Beq[i] = elm.Beq
        data.m[i] = elm.m
        data.theta[i] = elm.theta
        # nc.Inom[i] = (elm.rate / nc.Sbase) / np.abs(nc.Vbus[f])
        data.Pfset[i] = elm.Pdc_set
        data.Qtset[i] = elm.Qac_set
        data.Vac_set[i] = elm.Vac_set
        data.Vdc_set[i] = elm.Vdc_set
        data.control_mode[i] = elm.control_mode

        data.C_vsc_bus[i, f] = 1
        data.C_vsc_bus[i, t] = 1

    return data


def get_upfc_data(circuit: MultiCircuit, bus_dict, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :return:
    """
    data = UpfcData(nelm=len(circuit.upfc_devices), nbus=len(circuit.buses), ntime=ntime)

    # UPFC
    for i, elm in enumerate(circuit.upfc_devices):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        if time_series:
            data.active[i, :] = elm.active_prof
        else:
            data.active[i] = elm.active

        # vsc values
        data.names[i] = elm.name
        data.Rl[i] = elm.Rl
        data.Xl[i] = elm.Xl
        data.Bl[i] = elm.Bl

        data.Rs[i] = elm.Rs
        data.Xs[i] = elm.Xs

        data.Rsh[i] = elm.Rsh
        data.Xsh[i] = elm.Xsh

        data.Pset[i] = elm.Pfset
        data.Qset[i] = elm.Qfset
        data.Vsh[i] = elm.Vsh

        data.C_elm_bus[i, f] = 1
        data.C_elm_bus[i, t] = 1

    return data


def get_dc_line_data(circuit: MultiCircuit, bus_dict,
                     apply_temperature, branch_tolerance_mode: BranchImpedanceMode, time_series=False, ntime=1):
    """

    :param circuit:
    :param bus_dict:
    :param apply_temperature:
    :param branch_tolerance_mode:
    :return:
    """
    data = DcLinesData(ndcline=len(circuit.dc_lines), nbus=len(circuit.buses), ntime=ntime)

    # DC-lines
    for i, elm in enumerate(circuit.dc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        if time_series:
            data.active[i, :] = elm.active_prof
        else:
            data.active[i] = elm.active

        # dc line values
        data.names[i] = elm.name

        if apply_temperature:
            data.R[i] = elm.R_corrected
        else:
            data.R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[i] *= (1 + elm.tolerance / 100.0)

        data.impedance_tolerance[i] = elm.tolerance
        data.C_dc_line_bus[i, f] = 1
        data.C_dc_line_bus[i, t] = 1
        data.F[i] = f
        data.T[i] = t

        # Thermal correction
        data.temp_base[i] = elm.temp_base
        data.temp_oper[i] = elm.temp_oper
        data.alpha[i] = elm.alpha

    return data


def get_branch_data(circuit: MultiCircuit, bus_dict, Vbus, apply_temperature,
                    branch_tolerance_mode: BranchImpedanceMode,
                    time_series=False, opf=False, ntime=1,
                    opf_results: "OptimalPowerFlowResults" = None,
                    use_stored_guess=False):
    """

    :param circuit:
    :param bus_dict:
    :param Vbus: Array of bus voltages to be modified
    :param apply_temperature:
    :param branch_tolerance_mode:
    :param time_series:
    :param opf:
    :param ntime:
    :return:
    """
    nline = len(circuit.lines)
    ntr = len(circuit.transformers2w)
    nvsc = len(circuit.vsc_devices)
    nupfc = len(circuit.upfc_devices)
    ndcline = len(circuit.dc_lines)
    nbr = nline + ntr + nvsc + ndcline + nupfc

    if opf:
        data = BranchOpfData(nbr=nbr, nbus=len(circuit.buses), ntime=ntime)
    else:
        data = BranchData(nbr=nbr, nbus=len(circuit.buses), ntime=ntime)

    # Compile the lines
    for i, elm in enumerate(circuit.lines):
        # generic stuff
        data.names[i] = elm.name
        data.codes[i] = elm.code

        if time_series:
            data.active[i, :] = elm.active_prof
            data.rates[i, :] = elm.rate_prof
            data.contingency_rates[i, :] = elm.rate_prof * elm.contingency_factor_prof

            if opf:
                data.branch_cost[i, :] = elm.Cost_prof

        else:
            data.active[i] = elm.active
            data.rates[i] = elm.rate
            data.contingency_rates[i] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[i] = elm.Cost

        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]
        data.C_branch_bus_f[i, f] = 1
        data.C_branch_bus_t[i, t] = 1
        data.F[i] = f
        data.T[i] = t

        if apply_temperature:
            data.R[i] = elm.R_corrected
        else:
            data.R[i] = elm.R

        if branch_tolerance_mode == BranchImpedanceMode.Lower:
            data.R[i] *= (1 - elm.tolerance / 100.0)
        elif branch_tolerance_mode == BranchImpedanceMode.Upper:
            data.R[i] *= (1 + elm.tolerance / 100.0)

        data.X[i] = elm.X
        data.B[i] = elm.B

        data.R0[i] = elm.R0
        data.X0[i] = elm.X0
        data.B0[i] = elm.B0

        data.R2[i] = elm.R2
        data.X2[i] = elm.X2
        data.B2[i] = elm.B2

        # data.conn[i] = elm.conn

        data.contingency_enabled[i] = int(elm.contingency_enabled)
        data.monitor_loading[i] = int(elm.monitor_loading)

    # DC-lines
    offset = nline
    for i, elm in enumerate(circuit.dc_lines):
            ii = i + offset

            # generic stuff
            f = bus_dict[elm.bus_from]
            t = bus_dict[elm.bus_to]

            data.names[ii] = elm.name
            data.dc[ii] = 1

            if time_series:
                data.active[ii, :] = elm.active_prof
                data.rates[ii, :] = elm.rate_prof
                data.contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor_prof

                if opf:
                    data.branch_cost[ii, :] = elm.Cost_prof
            else:
                data.active[ii] = elm.active
                data.rates[ii] = elm.rate
                data.contingency_rates[ii] = elm.rate * elm.contingency_factor

                if opf:
                    data.branch_cost[ii] = elm.Cost

            data.C_branch_bus_f[ii, f] = 1
            data.C_branch_bus_t[ii, t] = 1
            data.F[ii] = f
            data.T[ii] = t

            data.contingency_enabled[ii] = int(elm.contingency_enabled)
            data.monitor_loading[ii] = int(elm.monitor_loading)

            if apply_temperature:
                data.R[ii] = elm.R_corrected
            else:
                data.R[ii] = elm.R

            if branch_tolerance_mode == BranchImpedanceMode.Lower:
                data.R[ii] *= (1 - elm.tolerance / 100.0)
            elif branch_tolerance_mode == BranchImpedanceMode.Upper:
                data.R[ii] *= (1 + elm.tolerance / 100.0)

    # 2-winding transformers
    offset += ndcline
    for i, elm in enumerate(circuit.transformers2w):
        ii = i + offset

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name

        if time_series:
            data.active[ii, :] = elm.active_prof
            data.rates[ii, :] = elm.rate_prof
            data.contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor_prof

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii, :] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R
        data.X[ii] = elm.X
        data.G[ii] = elm.G
        data.B[ii] = elm.B

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0
        data.G0[ii] = elm.G0
        data.B0[ii] = elm.B0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2
        data.G2[ii] = elm.G2
        data.B2[ii] = elm.B2

        data.conn[ii] = elm.conn

        if time_series:
            if opf_results is not None:
                data.m[ii] = elm.tap_module
                data.theta[ii, :] = opf_results.phase_shift[:, ii]
            else:
                data.m[ii] = elm.tap_module_prof
                data.theta[ii, :] = elm.angle_prof
        else:
            if opf_results is not None:
                data.m[ii] = elm.tap_module
                data.theta[ii] = opf_results.phase_shift[ii]
            else:
                data.m[ii] = elm.tap_module
                data.theta[ii] = elm.angle

        data.m_min[ii] = elm.tap_module_min
        data.m_max[ii] = elm.tap_module_max
        data.theta_min[ii] = elm.angle_min
        data.theta_max[ii] = elm.angle_max

        data.Pfset[ii] = elm.Pset

        data.control_mode[ii] = elm.control_mode
        data.tap_f[ii], data.tap_t[ii] = elm.get_virtual_taps()

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        if not use_stored_guess:
            if elm.control_mode == TransformerControlType.Vt:
                Vbus[t] = elm.vset

            elif elm.control_mode == TransformerControlType.PtVt:  # 2a:Vdc
                Vbus[t] = elm.vset

    # VSC
    offset += ntr
    for i, elm in enumerate(circuit.vsc_devices):
        ii = i + offset

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name

        if time_series:
            data.active[ii, :] = elm.active_prof
            data.rates[ii, :] = elm.rate_prof
            data.contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor_prof

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.R1
        data.X[ii] = elm.X1

        data.R0[ii] = elm.R0
        data.X0[ii] = elm.X0

        data.R2[ii] = elm.R2
        data.X2[ii] = elm.X2

        data.G0sw[ii] = elm.G0sw
        data.Beq[ii] = elm.Beq
        data.m[ii] = elm.m
        data.m_max[ii] = elm.m_max
        data.m_min[ii] = elm.m_min
        data.alpha1[ii] = elm.alpha1
        data.alpha2[ii] = elm.alpha2
        data.alpha3[ii] = elm.alpha3
        data.k[ii] = elm.k  # 0.8660254037844386  # sqrt(3)/2 (do not confuse with k droop)

        if time_series:
            if opf_results is not None:
                data.theta[ii, :] = opf_results.phase_shift[:, ii]
            else:
                data.theta[ii, :] = elm.theta
        else:
            if opf_results is not None:
                data.theta[ii] = opf_results.phase_shift[ii]
            else:
                data.theta[ii] = elm.theta

        data.theta_min[ii] = elm.theta_min
        data.theta_max[ii] = elm.theta_max
        data.Pfset[ii] = elm.Pdc_set
        data.Qtset[ii] = elm.Qac_set
        data.Kdp[ii] = elm.kdp
        data.vf_set[ii] = elm.Vac_set
        data.vt_set[ii] = elm.Vdc_set
        data.control_mode[ii] = elm.control_mode
        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

        '''
        type_0_free = '0:Free'
        type_I_1 = '1:Vac'
        type_I_2 = '2:Pdc+Qac'
        type_I_3 = '3:Pdc+Vac'
        type_II_4 = '4:Vdc+Qac'
        type_II_5 = '5:Vdc+Vac'
        type_III_6 = '6:Droop+Qac'
        type_III_7 = '7:Droop+Vac'
        '''

        if not use_stored_guess:
            if elm.control_mode == ConverterControlType.type_I_1:  # 1a:Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_I_3:  # 3:Pdc+Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_II_4:  # 4:Vdc+Qac
                Vbus[f] = elm.Vdc_set

            elif elm.control_mode == ConverterControlType.type_II_5:  # 5:Vdc+Vac
                Vbus[f] = elm.Vdc_set
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_III_7:  # 7:Droop+Vac
                Vbus[t] = elm.Vac_set

            elif elm.control_mode == ConverterControlType.type_IV_I:  # 8:Vdc
                Vbus[f] = elm.Vdc_set

    # UPFC
    offset += nvsc
    for i, elm in enumerate(circuit.upfc_devices):
        ii = i + offset

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        data.names[ii] = elm.name

        if time_series:
            data.active[ii, :] = elm.active_prof
            data.rates[ii, :] = elm.rate_prof
            data.contingency_rates[ii, :] = elm.rate_prof * elm.contingency_factor_prof

            if opf:
                data.branch_cost[ii, :] = elm.Cost_prof
        else:
            data.active[ii] = elm.active
            data.rates[ii] = elm.rate
            data.contingency_rates[ii] = elm.rate * elm.contingency_factor

            if opf:
                data.branch_cost[ii] = elm.Cost

        data.C_branch_bus_f[ii, f] = 1
        data.C_branch_bus_t[ii, t] = 1
        data.F[ii] = f
        data.T[ii] = t

        data.R[ii] = elm.Rs
        data.X[ii] = elm.Xs

        data.R0[ii] = elm.Rs0
        data.X0[ii] = elm.Xs0

        data.R2[ii] = elm.Rs2
        data.X2[ii] = elm.Xs2

        ysh1 = elm.get_ysh1()
        data.Beq[ii] = ysh1.imag

        data.Pfset[ii] = elm.Pfset

        data.contingency_enabled[ii] = int(elm.contingency_enabled)
        data.monitor_loading[ii] = int(elm.monitor_loading)

    return data


def get_hvdc_data(circuit: MultiCircuit, bus_dict, bus_types, time_series=False, ntime=1,
                  opf_results: "OptimalPowerFlowResults" = None):
    """

    :param circuit:
    :param bus_dict:
    :param bus_types:
    :param time_series:
    :param ntime:
    :param opf_results:
    :return:
    """
    data = HvdcData(nhvdc=len(circuit.hvdc_lines), nbus=len(circuit.buses), ntime=ntime)

    # HVDC
    for i, elm in enumerate(circuit.hvdc_lines):

        # generic stuff
        f = bus_dict[elm.bus_from]
        t = bus_dict[elm.bus_to]

        # hvdc values
        data.names[i] = elm.name
        data.dispatchable[i] = int(elm.dispatchable)

        if time_series:
            data.active[i, :] = elm.active_prof
            data.rate[i, :] = elm.rate_prof
            data.contingency_rate[i, :] = elm.rate_prof * elm.contingency_factor_prof
            data.angle_droop[i, :] = elm.angle_droop_prof

            if opf_results is not None:
                data.Pset[i, :] = -opf_results.hvdc_Pf[:, i]
            else:
                data.Pset[i, :] = elm.Pset_prof

            data.Vset_f[i, :] = elm.Vset_f_prof
            data.Vset_t[i, :] = elm.Vset_t_prof
        else:
            data.active[i] = elm.active
            data.rate[i] = elm.rate
            data.contingency_rate[i] = elm.rate * elm.contingency_factor
            data.angle_droop[i] = elm.angle_droop
            data.r[i] = elm.r

            if opf_results is not None:
                data.Pset[i] = -opf_results.hvdc_Pf[i]
                data.Pt[i] = opf_results.hvdc_Pf[i]
            else:
                data.Pset[i] = elm.Pset

            data.Vset_f[i] = elm.Vset_f
            data.Vset_t[i] = elm.Vset_t

        data.control_mode[i] = elm.control_mode

        data.Qmin_f[i] = elm.Qmin_f
        data.Qmax_f[i] = elm.Qmax_f
        data.Qmin_t[i] = elm.Qmin_t
        data.Qmax_t[i] = elm.Qmax_t

        # hack the bus types to believe they are PV
        if elm.active:
            bus_types[f] = BusMode.PV.value
            bus_types[t] = BusMode.PV.value

        # the the bus-hvdc line connectivity
        data.C_hvdc_bus_f[i, f] = 1
        data.C_hvdc_bus_t[i, t] = 1

    return data
