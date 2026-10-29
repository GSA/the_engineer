"""Literal evidence presentation, without invented semantics."""
import json
from .packet import validate_packet


def render_report(packet,validation=None):
    validate_packet(packet)
    if validation is not None:
        if validation.get('packet_digest')!=packet['digest'] or validation.get('task')!=packet['task']:
            raise ValueError('revalidation handoff mismatch')
    lines=[f"Task context: {packet['readiness']} (historical observation)",
           f"Task: {json.dumps(packet['task'],sort_keys=True)}",f"Packet: {packet['digest']}",
           'Evidence inherits source handling; do not paste into public PR/task bodies.',
           'Readiness is not authorization. Revalidate immediately before action.',
           f"Providers: {json.dumps(packet['providers'],sort_keys=True)}"]
    for index,entry in enumerate(packet['business']):
        response=entry['response']
        lines.append(f'Business {index}: '+('missing' if response is None else json.dumps({k:v for k,v in response.items() if k!='pieces'},sort_keys=True)))
        if response:
            for piece in response.get('pieces',[]):
                lines.append(f"  {piece['locator']} (indexed {piece['path']}:{piece['line_start']}-{piece['line_end']}; hash {piece['source_hash']})")
                if 'source_location' in piece:
                    # Rendition pieces index extraction JSON, so the indexed range above
                    # is not the original location a citation must name.
                    lines.append(f"  Original source location: {json.dumps(piece['source_location'],sort_keys=True,ensure_ascii=False)}")
                rest={k:v for k,v in piece.items() if k not in ('locator','path','line_start','line_end','source_hash','text','reasons','source_location')}
                if rest: lines.append(f"  Provenance: {json.dumps(rest,sort_keys=True,ensure_ascii=False)}")
                lines.extend([f"  Qualifications: {json.dumps(piece.get('reasons',[]))}",piece['text']])
    for index,entry in enumerate(packet['code']):
        lines.append(f"Code {index}: {json.dumps(entry['response'],sort_keys=True,ensure_ascii=False)}")
    lines += [f"Associations (presentation only): {json.dumps(packet['associations'],sort_keys=True)}",
              f"Capabilities: {json.dumps(packet['capabilities'],sort_keys=True)}",
              f"Scope issues: {json.dumps(packet['issues'],sort_keys=True)}"]
    if validation is not None: lines.append('Point-in-time revalidation: '+json.dumps(validation,sort_keys=True))
    return '\n'.join(lines)
