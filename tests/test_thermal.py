"""Independent thermal/hydraulic solutions; no production RHS builds oracles."""
from dataclasses import FrozenInstanceError, asdict, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import math
import json
import unittest
import numpy as np
from scipy.linalg import expm
from fluidlab.thermal import (ThermalInputs, ThermalParameters, ThermalPlant, ThermalSolverConfig,
                              hydraulic_operating_point, IntegrationFailure, PlantStopped)


TIGHT = ThermalSolverConfig(method="DOP853", rtol=1e-11, atol=(1e-11,)*5+(1e-8,)*2)


class HydraulicTests(unittest.TestCase):
    def test_independent_pressure_substitution_forward_and_restricted(self):
        p = ThermalParameters()
        for speed, opening in ((1, 1), (.5274982823, .65), (.8, .1), (.1, .01)):
            point = hydraulic_operating_point(speed, opening, p)
            expected_flow = math.sqrt(100000*speed**2 / (4e11+6e11+1e11/opening**2))
            pump = 100000*speed**2 - 4e11*point.flow_m3_s**2
            system = (6e11+1e11/opening**2)*point.flow_m3_s**2
            self.assertAlmostEqual(point.flow_m3_s, expected_flow, places=14)
            self.assertLess(abs(pump-system)/100000, 1e-8)
            self.assertAlmostEqual(point.pump_pressure_pa, system, places=8)
        self.assertLess(hydraulic_operating_point(.8, .1).flow_m3_s,
                        hydraulic_operating_point(.8, .65).flow_m3_s)

    def test_zero_speed_and_closed_branch_have_no_leak(self):
        for speed, opening, pressure in ((0, .65, 0), (.5, 0, 25000), (0, 0, 0)):
            point = hydraulic_operating_point(speed, opening)
            self.assertEqual(point.flow_m3_s, 0)
            self.assertEqual(point.pump_pressure_pa, pressure)

    def test_tiny_opening_is_finite_and_stable(self):
        for opening in (1e-6, 1e-50, 1e-300):
            point = hydraulic_operating_point(.5, opening)
            self.assertGreater(point.flow_m3_s, 0)
            self.assertAlmostEqual(point.flow_m3_s/opening, .5*math.sqrt(100000/1e11), places=12)
            self.assertTrue(math.isfinite(point.pump_pressure_pa))
        no_loss = ThermalInputs(valve_resistance_pa_s2_m6=0)
        point = hydraulic_operating_point(.5, 1e-300, inputs=no_loss)
        self.assertAlmostEqual(point.flow_m3_s, .5*math.sqrt(100000/1e12), places=14)

    def test_explicit_held_resistance_override_updates_observable_flow(self):
        plant = ThermalPlant(pump_speed=.5, valve_opening=.65)
        initial = plant.flow_m3_s
        inputs = ThermalInputs(pump_command=.5, valve_command=.65, pipe_resistance_pa_s2_m6=18e11)
        plant.advance(.1, inputs)
        expected = math.sqrt(100000*.5**2/(4e11+18e11+1e11/.65**2))
        self.assertLess(plant.flow_m3_s, initial)
        self.assertAlmostEqual(plant.flow_m3_s, expected, places=14)
        self.assertIs(plant.last_held_inputs, inputs)

    def test_imposed_flow_benchmark_does_not_claim_hydraulic_pressure(self):
        plant = ThermalPlant(imposed_flow_m3_s=.00015)
        self.assertEqual(plant.flow_m3_s, .00015)
        self.assertIsNone(plant.pump_pressure_pa)
        advanced = plant.advance(.1, ThermalInputs())
        self.assertEqual(advanced.diagnostics["flow_mode"], "imposed_flow_benchmark")


class ThermalPhysicsTests(unittest.TestCase):
    def test_isolated_constant_heating_matches_linear_solution(self):
        p = replace(ThermalParameters(), hot_conductance_w_k=0, sink_conductance_w_k=0)
        plant = ThermalPlant(p, valve_opening=0)
        errors = []
        for tick in range(1, 11):
            plant.advance(10, ThermalInputs(heat_command=1, valve_command=0), TIGHT)
            expected = 293.15 + 5000*(tick*10)/10000
            errors.append(abs(plant.y[0]-expected))
            self.assertAlmostEqual(plant.y[5], 5000*(tick*10), places=5)
        self.assertLess(max(errors), 1e-5)

    def test_isolated_sink_cooling_matches_exponential_solution(self):
        p = replace(ThermalParameters(), hot_conductance_w_k=0)
        plant = ThermalPlant(p, cold_temperature_k=330, valve_opening=0)
        errors = []
        for tick in range(1, 11):
            plant.advance(10, ThermalInputs(valve_command=0), TIGHT)
            expected = 283.15 + (330-283.15)*math.exp(-500*(tick*10)/(3*4180))
            errors.append(abs(plant.y[2]-expected))
        self.assertLess(max(errors), 1e-5)

    def test_independent_matrix_exponential_and_1200_second_equilibrium(self):
        # Independently assembled from three balances and frozen raw constants.
        a = np.array([[-300/10000, 300/10000, 0],
                      [300/8360, -(300+627)/8360, 627/8360],
                      [0, 627/12540, -(627+500)/12540]])
        steady = np.array([283.15+5000/500+5000/627+5000/300,
                           283.15+5000/500+5000/627, 283.15+5000/500])
        plant = ThermalPlant(imposed_flow_m3_s=.00015)
        errors = []
        for tick in range(1, 13):
            plant.advance(100, ThermalInputs(heat_command=1), TIGHT)
            expected = steady + expm(a*(tick*100)) @ (np.full(3, 293.15)-steady)
            errors.append(float(np.max(np.abs(plant.y[:3]-expected))))
        self.assertLess(max(errors), 1e-5)
        self.assertLess(float(np.max(np.abs(plant.y[:3]-steady))), .01)

    def test_closed_internal_mixing_conserves_independent_weighted_energy(self):
        p = replace(ThermalParameters(), sink_conductance_w_k=0)
        plant = ThermalPlant(p, wall_temperature_k=340, hot_temperature_k=310,
                             cold_temperature_k=290, imposed_flow_m3_s=.00015)
        weights = np.array([10000, 8360, 12540])
        initial = float(weights @ plant.y[:3])
        errors = []
        for _ in range(10):
            plant.advance(10, ThermalInputs(), TIGHT)
            errors.append(abs(float(weights @ plant.y[:3])-initial))
        self.assertLess(max(errors), 1e-3)

    def test_no_flow_internal_wall_exchange_cancels(self):
        p = replace(ThermalParameters(), sink_conductance_w_k=0)
        plant = ThermalPlant(p, wall_temperature_k=340, hot_temperature_k=290, valve_opening=0)
        initial = 10000*340 + 8360*290
        plant.advance(100, ThermalInputs(valve_command=0), TIGHT)
        self.assertLess(abs(10000*plant.y[0]+8360*plant.y[1]-initial), 1e-3)
        self.assertEqual(plant.y[2], 293.15)
        self.assertGreater(plant.y[1], 290)
        self.assertLess(plant.y[0], 340)

    def test_augmented_energy_residual_is_consistency_only(self):
        plant = ThermalPlant()
        for command in (.2, .8, 0):
            plant.advance(20, ThermalInputs(heat_command=command, pump_command=.5), TIGHT)
        self.assertLess(abs(plant.energy_residual_j()), 1e-3)
        independent_change = (10000*(plant.y[0]-293.15)+8360*(plant.y[1]-293.15)+12540*(plant.y[2]-293.15))
        self.assertLess(abs(independent_change-(plant.y[5]-plant.y[6])), 1e-3)

    def test_zero_flow_with_heat_has_no_flowing_steady_state(self):
        plant = ThermalPlant(valve_opening=0)
        plant.advance(60, ThermalInputs(heat_command=1, valve_command=0), TIGHT)
        self.assertEqual(plant.flow_m3_s, 0)
        # No outlet from wall/hot subsystem: its total energy keeps growing Pt.
        gain = 10000*(plant.y[0]-293.15) + 8360*(plant.y[1]-293.15)
        self.assertLess(abs(gain-5000*60), 1e-3)
        self.assertGreater(plant.y[0], 293.15)
        self.assertGreater(plant.y[1], 293.15)

    def test_upper_event_matches_analytic_time_and_remains_stopped(self):
        p = replace(ThermalParameters(), hot_conductance_w_k=0, sink_conductance_w_k=0)
        plant = ThermalPlant(p, valve_opening=0)
        advanced = plant.advance(200, ThermalInputs(heat_command=1, valve_command=0), TIGHT)
        self.assertEqual(advanced.boundary, "wall_upper")
        self.assertAlmostEqual(advanced.time_s, (368.15-293.15)*10000/5000, places=7)
        self.assertIn("boundary_root_tolerance_k", advanced.diagnostics)
        state, time = plant.y.copy(), plant.t
        with self.assertRaises(PlantStopped):
            plant.advance(1, ThermalInputs())
        np.testing.assert_array_equal(plant.y, state)
        self.assertEqual(plant.t, time)

    def test_lower_maximum_principle_finite_horizon_cooling(self):
        p = replace(ThermalParameters(), hot_conductance_w_k=0, sink_temperature_k=273.15)
        plant = ThermalPlant(p, cold_temperature_k=300, valve_opening=0)
        advanced = plant.advance(100, ThermalInputs(valve_command=0), TIGHT)
        expected = 273.15+(300-273.15)*math.exp(-500*100/12540)
        self.assertIsNone(advanced.boundary)
        self.assertGreater(plant.y[2], 273.15)
        self.assertLess(abs(plant.y[2]-expected), 1e-5)

    def test_legal_stationary_actuator_endpoints_never_terminate(self):
        for endpoint in (0, 1):
            plant = ThermalPlant(pump_speed=endpoint, valve_opening=endpoint)
            advanced = plant.advance(1, ThermalInputs(pump_command=endpoint, valve_command=endpoint))
            self.assertIsNone(advanced.boundary)
            self.assertFalse(plant.stopped)
            self.assertEqual(plant.y[3], endpoint)
            self.assertEqual(plant.y[4], endpoint)


class ThermalContractTests(unittest.TestCase):
    def test_parameter_and_solver_field_sets_match_versioned_contract(self):
        root = Path(__file__).resolve().parents[1]
        params = json.loads((root/"schemas/thermal-model-v1.schema.json").read_text(encoding="utf-8"))
        solver = json.loads((root/"schemas/thermal-solver-v1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(asdict(ThermalParameters())), set(params["required"]))
        executed = ThermalSolverConfig().executed(.1)
        self.assertEqual(set(executed), set(solver["required"]))
        self.assertEqual(executed["state_order"], solver["properties"]["state_order"]["const"])
        self.assertEqual(executed["state_units"], solver["properties"]["state_units"]["const"])
        self.assertEqual(len(executed["atol"]), 7)

    def test_parameters_allow_zero_analytic_conductances_and_reject_bad_values(self):
        ThermalParameters(hot_conductance_w_k=0, sink_conductance_w_k=0, max_heat_w=0)
        for value in (True, "1000", 0, -1, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ThermalParameters(density_kg_m3=value)
        for changes in (dict(sink_temperature_k=273), dict(sink_temperature_k=368.15),
                        dict(pump_curve_pa_s2_m6=0), dict(hot_conductance_w_k=-1),
                        dict(sink_conductance_w_k=True), dict(version=True)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ThermalParameters(**changes)

    def test_initial_temperature_and_actuator_guards(self):
        for value in (273.15, 368.15, float("nan"), True, "293.15"):
            for field in ("wall_temperature_k", "hot_temperature_k", "cold_temperature_k"):
                with self.subTest(value=value, field=field), self.assertRaises(ValueError):
                    ThermalPlant(**{field: value})
        for field in ("pump_speed", "valve_opening"):
            for value in (-.1, 1.1, True):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    ThermalPlant(**{field: value})

    def test_inputs_and_solver_are_immutable_and_strict(self):
        inputs = ThermalInputs()
        with self.assertRaises(FrozenInstanceError):
            inputs.heat_command = 1
        for changes in (dict(heat_command=True), dict(pump_command=-1), dict(valve_command=1.1),
                        dict(sink_conductance_w_k=float("nan")), dict(valve_resistance_pa_s2_m6=-1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ThermalInputs(**changes)
        ThermalInputs(sink_conductance_w_k=0, valve_resistance_pa_s2_m6=0)
        tolerances = [1e-10]*7
        solver = ThermalSolverConfig(atol=tolerances)
        tolerances[0] = 1
        self.assertEqual(solver.atol[0], 1e-10)
        with self.assertRaises(FrozenInstanceError):
            solver.rtol = .1
        for changes in (dict(atol=[1e-8]*5), dict(atol=[True]*7), dict(rtol=float("nan")),
                        dict(rtol=True), dict(max_step_s=.1), dict(method="BDF")):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                ThermalSolverConfig(**changes)

    @staticmethod
    def partial_result(success=False):
        state = np.array([[293.15, 293.15], [293.15, 293.15], [293.15, 293.15],
                          [0, 0], [.65, .65], [0, 0], [0, 0]])
        return SimpleNamespace(success=success, status=0 if success else -1, message="synthetic partial result",
                               nfev=7, njev=0, nlu=0, t=np.array([0, .04]), y=state,
                               t_events=tuple(np.array([]) for _ in range(6)))

    def test_partial_failure_preserves_last_state_diagnostics_and_latch(self):
        plant = ThermalPlant()
        with patch("fluidlab.thermal.solve_ivp", return_value=self.partial_result()), self.assertRaises(IntegrationFailure) as error:
            plant.advance(.1, ThermalInputs())
        self.assertEqual(plant.t, .04)
        self.assertEqual(error.exception.advance.diagnostics["nfev"], 7)
        self.assertEqual(len(error.exception.advance.diagnostics["partial_trace"]), 2)
        with self.assertRaises(PlantStopped):
            plant.advance(.1, ThermalInputs())

    def test_corrupt_accepted_temperature_or_actuator_state_is_not_clamped(self):
        for state_index, value in ((0, 368.16), (1, 273.14), (3, -.01), (4, 1.01)):
            result = self.partial_result(success=True)
            result.y[state_index, -1] = value
            plant = ThermalPlant()
            with patch("fluidlab.thermal.solve_ivp", return_value=result), self.assertRaises(IntegrationFailure) as error:
                plant.advance(.1, ThermalInputs())
            self.assertEqual(plant.t, 0)
            self.assertEqual(error.exception.advance.diagnostics["rejected_solver_sample"]["state"][state_index], value)
            self.assertTrue(plant.stopped)

    def test_reported_lower_root_has_raw_residual_and_persistent_stop(self):
        # Synthetic event tests guard semantics, not a finite cooling-time claim.
        result = self.partial_result(success=True)
        result.y[2, -1] = math.nextafter(273.15, -math.inf)
        result.t_events = (np.array([]), np.array([]), np.array([]), np.array([]), np.array([.04]), np.array([]))
        plant = ThermalPlant()
        with patch("fluidlab.thermal.solve_ivp", return_value=result):
            advanced = plant.advance(.1, ThermalInputs())
        self.assertEqual(advanced.boundary, "cold_lower")
        self.assertLess(plant.y[2], 273.15)
        self.assertLess(advanced.diagnostics["boundary_residuals_k"]["cold_lower"], 0)
        with self.assertRaises(PlantStopped):
            plant.advance(.1, ThermalInputs())

    def test_solver_exception_retains_prior_state(self):
        plant = ThermalPlant()
        with patch("fluidlab.thermal.solve_ivp", side_effect=RuntimeError("forced failure")), self.assertRaises(IntegrationFailure) as error:
            plant.advance(.1, ThermalInputs())
        self.assertEqual(plant.t, 0)
        self.assertEqual(error.exception.advance.diagnostics["exception_type"], "RuntimeError")
        self.assertTrue(plant.stopped)


if __name__ == "__main__":
    unittest.main()
