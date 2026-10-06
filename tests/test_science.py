"""Independent analytic oracles plus behavior-oriented software tests."""
import math, unittest
from dataclasses import replace
import numpy as np
from fluidlab.plant import Plant,Parameters,drain_flow
from fluidlab.control import PIController,Supervisor,Observation
from fluidlab.runner import run


class PhysicsTests(unittest.TestCase):
    def test_linear_fill(self):
        p=Parameters();plant=Plant(p,h0_m=.25,q0_m3_s=p.pump_max_m3_s,valve0=0.)
        plant.advance(20.,1.,0.)
        self.assertAlmostEqual(plant.y[0],.25+p.pump_max_m3_s*20/p.area_m2,places=10)

    def test_gravity_drain_analytic(self):
        p=Parameters();plant=Plant(p,h0_m=.8,valve0=1.)
        plant.advance(100.,0.,1.)
        coefficient=p.discharge_coefficient*p.outlet_area_m2*math.sqrt(2*p.gravity_m_s2)
        expected=(math.sqrt(.8)-coefficient*100/(2*p.area_m2))**2
        self.assertAlmostEqual(plant.y[0],expected,places=8)

    def test_pump_lag_and_integrated_volume(self):
        p=Parameters();plant=Plant(p,valve0=0.)
        t=3.;u=.5;plant.advance(t,u,0.)
        q=p.pump_max_m3_s*u*(1-math.exp(-t/p.pump_tau_s))
        volume=p.pump_max_m3_s*u*(t-p.pump_tau_s*(1-math.exp(-t/p.pump_tau_s)))
        self.assertAlmostEqual(plant.y[1],q,places=10)
        self.assertAlmostEqual(plant.y[0],.25+volume/p.area_m2,places=9)

    def test_volume_conservation(self):
        plant=Plant()
        for u in [0.,.8,.2,1.,.4]: plant.advance(10,u,.6)
        self.assertLess(abs(plant.volume_residual_m3()),1e-10)

    def test_terminal_full_not_clipped(self):
        p=Parameters();plant=Plant(p,h0_m=.9,q0_m3_s=p.pump_max_m3_s,valve0=0.)
        result=plant.advance(50,1,0)
        self.assertEqual(result.boundary,"full")
        self.assertAlmostEqual(result.time_s,p.area_m2*.1/p.pump_max_m3_s,places=7)
        self.assertAlmostEqual(result.state[0],1.,places=9)

    def test_terminal_empty_matches_analytic_time(self):
        p=Parameters();plant=Plant(p,h0_m=.25,valve0=1.)
        result=plant.advance(1000,0,1,rtol=1e-9,atol=[1e-11]*5)
        expected=2*p.area_m2*math.sqrt(.25)/(p.discharge_coefficient*p.outlet_area_m2*math.sqrt(2*p.gravity_m_s2))
        self.assertEqual(result.boundary,"empty")
        self.assertLess(abs(result.time_s-expected),.01)

    def test_independent_solver_agreement(self):
        a,b=Plant(),Plant()
        a.advance(30,.65,.4,method="RK45")
        b.advance(30,.65,.4,method="DOP853",rtol=1e-10,atol=[1e-12]*5)
        self.assertLess(np.max(np.abs(a.y-b.y)),1e-7)

    def test_parameter_validation(self):
        for bad in [0,-1,float("nan"),float("inf")]:
            with self.subTest(bad=bad),self.assertRaises(ValueError): Parameters(area_m2=bad)

    def test_drain_scaling(self):
        p=Parameters()
        self.assertAlmostEqual(drain_flow(.8,1,p)/drain_flow(.2,1,p),2.)
        self.assertAlmostEqual(drain_flow(.2,.5,p)/drain_flow(.2,1,p),.5)


class ControlTests(unittest.TestCase):
    def test_anti_windup_and_recovery(self):
        ctrl=PIController()
        for _ in range(1000): ctrl.update(2.,0.,.1)
        self.assertEqual(ctrl.integral,0.)
        self.assertEqual(ctrl.update(.1,.8,.1),0.)

    def test_stale_latch(self):
        s=Supervisor()
        self.assertTrue(s.update(1.,Observation(.5,0.,True,False)))
        self.assertTrue(s.update(2.,Observation(.5,2.,True,False)))
        self.assertEqual(s.reason,"stale_sensor")

    def test_invalid_samples(self):
        for obs in [Observation(float("nan"),0.,True,False),
                    Observation(.5,0.,False,False),Observation(.5,2.,True,False)]:
            with self.subTest(obs=obs): self.assertTrue(Supervisor().update(0.,obs))

    def test_high_switch_overrides_plausible_wrong_level(self):
        s=Supervisor();s.update(0.,Observation(.4,0.,True,True))
        self.assertEqual(s.reason,"high_high")


class ScenarioTests(unittest.TestCase):
    def cfg(self,**kw):
        return dict(name="test",duration_s=240.,dt_s=.1,fault="none",expected="nominal",**kw)

    def test_nominal(self):
        _,summary=run(self.cfg());self.assertTrue(summary["all_checks_pass"],summary)

    def test_dropout(self):
        c=self.cfg();c.update(fault="sensor_dropout",expected="stale_trip",fault_at_s=60.)
        _,summary=run(c);self.assertTrue(summary["all_checks_pass"],summary)

    def test_blockage(self):
        c=self.cfg();c.update(fault="blocked_outlet",expected="contained",fault_at_s=60.)
        _,summary=run(c);self.assertTrue(summary["all_checks_pass"],summary)

    def test_biased_sensor_trip_and_coast(self):
        c=self.cfg();c.update(fault="sensor_bias_ramp",expected="high_trip",fault_at_s=60.)
        rows,summary=run(c);self.assertTrue(summary["all_checks_pass"],summary)
        first=next(r for r in rows if r["trip"])
        self.assertGreater(first["flow_m3_s"],0.) # coast persists after stop command

    def test_stuck_pump_exposes_uncontained_hazard(self):
        c=self.cfg();c.update(fault="pump_stuck_on",expected="observe_hazard",fault_at_s=60.)
        _,summary=run(c);self.assertTrue(summary["all_checks_pass"],summary)
        self.assertEqual(summary["boundary"],"full")

    def test_deterministic_noise_replay(self):
        c=self.cfg(sensor_noise_std_m=.002,seed=18);c.update(duration_s=10.,expected="characterize")
        a,_=run(c);b,_=run(c);self.assertEqual(a,b)

    def test_control_tick_refinement(self):
        a=self.cfg();b=self.cfg();b["dt_s"]=.05
        rows_a,_=run(a);rows_b,_=run(b)
        self.assertLess(max(abs(x["level_m"]-y["level_m"]) for x,y in zip(rows_a,rows_b[::2])),.002)


if __name__ == "__main__": unittest.main()
