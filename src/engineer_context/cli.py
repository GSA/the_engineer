"""Local CLI; no implicit persistence or task lifecycle mutations."""
import argparse
import asyncio
import json
from pathlib import Path
import sys
from .collect import collect
from .config import load_config, parse_task
from .packet import validate_packet
from .report import render_report
from .revalidate import revalidate
from .storage import read_private_json,write_private_json


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    collection=commands.add_parser('collect')
    collection.add_argument('--config',required=True,type=Path)
    collection.add_argument('--request',required=True,type=Path)
    collection.add_argument('--output',required=True,type=Path)
    report=commands.add_parser('report'); report.add_argument('--packet',required=True,type=Path); report.add_argument('--json',action='store_true')
    report.add_argument('--max-bytes',type=int,default=1048576)
    validation=commands.add_parser('revalidate')
    for field in ['config','packet','task','output']: validation.add_argument('--'+field,required=True,type=Path)
    args=parser.parse_args(argv)
    try:
        if args.command=='report':
            if args.max_bytes<=0: raise ValueError('invalid report budget')
            value=read_private_json(args.packet,args.max_bytes); validate_packet(value)
            print(json.dumps(value,ensure_ascii=False) if args.json else render_report(value))
        else:
            config=load_config(args.config); maximum=config.limits.max_bytes
            if args.command=='collect':
                value=asyncio.run(collect(config,read_private_json(args.request,maximum)))
            else:
                value=asyncio.run(revalidate(config,read_private_json(args.packet,maximum),parse_task(read_private_json(args.task,maximum))))
            write_private_json(args.output,value,maximum)
            print('Readiness: '+value['readiness']+'; observation is not authorization')
        return 0 if value['readiness']=='ready' else 2
    except (ValueError,OSError):
        print('Invalid context input/configuration or private output failure',file=sys.stderr)
        return 1


if __name__=='__main__': raise SystemExit(main())
