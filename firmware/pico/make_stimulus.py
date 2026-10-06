"""Prepare an indicator-only hardware capture stimulus; never accesses a COM port."""
import argparse
import json
from pathlib import Path
from fluidlab.protocol import Configuration, Frame


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=("link","peripheral"),required=True)
    parser.add_argument("--epoch",type=int,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    records=[]
    def add(ms,frame):
        records.append(dict(offset_ms=ms,ascii=frame.encode().decode("ascii")))
    add(1000,Frame("H",args.epoch,0,"V",0,(1,)))
    add(1010,Frame("C",args.epoch,0,"V",0,Configuration().payload))
    if args.mode=="link":
        # Continue valid observations after intent stops: isolate intent_expired.
        for sequence in range(200):
            ms=1100+sequence*100
            source_us=sequence*100_000
            add(ms,Frame("O",args.epoch,sequence,"V",source_us,(1,1,490_000)))
            add(ms,Frame("O",args.epoch,sequence,"V",source_us,(6,1,0)))
            if sequence<100:
                add(ms,Frame("U",args.epoch,sequence,"V",source_us,(1 if sequence==0 else 0,0)))
    packet=dict(version=1,mode=args.mode,epoch=args.epoch,clock="host wall offsets; source V; device D independent",
                purpose="Indicator-only educational I/O; generated stimulus is not measured evidence",records=records)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(packet,indent=2)+"\n",encoding="utf-8")
    print(args.out)


if __name__=="__main__":
    main()
