from pathlib import Path
import argparse,json
from .runner import load_scenario,run,write_run


def main():
    parser = argparse.ArgumentParser(description="Educational fluid SIL bench")
    parser.add_argument("scenario",type=Path)
    parser.add_argument("--out",type=Path,default=Path("artifacts/run"))
    parser.add_argument("--solver",choices=["RK45","DOP853","Radau"],default="RK45")
    parser.add_argument("--plot",action="store_true")
    args = parser.parse_args()
    cfg=load_scenario(args.scenario)
    rows,summary=run(cfg,method=args.solver)
    write_run(args.out,cfg,rows,summary,args.solver)
    if args.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig,axes=plt.subplots(3,1,sharex=True,figsize=(9,7))
        t=[r["time_s"] for r in rows]
        axes[0].plot(t,[r["level_m"] for r in rows],label="True level")
        axes[0].plot(t,[r["measured_level_m"] for r in rows],label="Sensor",alpha=.7)
        axes[0].axhline(.8,color="red",ls="--",label="Independent high switch")
        axes[0].set_ylabel("Level (m)");axes[0].legend()
        axes[1].plot(t,[r["pump_command"] for r in rows],label="Requested pump")
        axes[1].plot(t,[r["applied_pump_command"] for r in rows],label="Applied pump",ls="--")
        axes[1].set_ylabel("Command (0–1)");axes[1].legend()
        axes[2].plot(t,[r["flow_m3_s"]*60000 for r in rows])
        axes[2].set_ylabel("Inflow (L/min)");axes[2].set_xlabel("Virtual time (s)")
        fig.suptitle(cfg["name"]+" — educational model; physical validation pending")
        fig.tight_layout();fig.savefig(args.out/"plot.png",dpi=160);plt.close(fig)
    print(json.dumps(summary,indent=2))
    return 0 if summary["all_checks_pass"] else 1


if __name__ == "__main__": raise SystemExit(main())
