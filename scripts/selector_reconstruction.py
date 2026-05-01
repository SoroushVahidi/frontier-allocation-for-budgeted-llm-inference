from __future__ import annotations
from typing import Any

def n(x: Any)->str: return str(x or '').strip().lower()

def reconstruct_groups(dr_row: dict[str,Any]) -> list[dict[str,Any]]:
    md=dr_row.get('result_metadata') or {}
    pool=(md.get('selector_candidate_pool') or md.get('final_branch_states') or dr_row.get('final_nodes') or [])
    pool=[x for x in pool if isinstance(x,dict)]
    groups={}
    for r in pool:
        ans=n(r.get('normalized_answer') or r.get('predicted_answer') or r.get('final_answer') or r.get('answer'))
        if not ans: continue
        g=groups.setdefault(ans,{'normalized_answer':ans,'support_count':0,'source_families':set(),'selected_votes':0})
        g['support_count'] += 1
        sf=n(r.get('source_family') or r.get('source') or r.get('source_id'))
        if sf: g['source_families'].add(sf)
        if int(r.get('is_original_selected') or 0)==1: g['selected_votes'] += 1
    out=[]
    for g in groups.values():
        g['source_family_count']=len(g['source_families'])
        g['source_families']=sorted(g['source_families'])
        out.append(g)
    return out

def support_only_choice(groups:list[dict[str,Any]], fallback:str='')->str:
    if not groups: return fallback
    return max(groups,key=lambda g:(g.get('support_count',0), g.get('normalized_answer','')))['normalized_answer']

def oracle_choice(groups:list[dict[str,Any]], gold:str, fallback:str='')->str:
    return gold if any(g.get('normalized_answer')==gold for g in groups) else fallback

def support_only_with_guard_v1_choice(current_answer:str, groups:list[dict[str,Any]]) -> tuple[str, dict[str,Any]]:
    sup = support_only_choice(groups, current_answer)
    cur = next((g for g in groups if g.get('normalized_answer') == current_answer), None)
    chal = next((g for g in groups if g.get('normalized_answer') == sup), None)
    blocked=[]
    chosen=current_answer
    if chal and chal.get('normalized_answer') != current_answer and chal.get('support_count',0) > (cur.get('support_count',0) if cur else 0):
        cflags=(chal.get('consistency_flags') or {}) if isinstance(chal,dict) else {}
        rflags=(cur.get('consistency_flags') or {}) if isinstance(cur,dict) else {}
        if sum(int(v) for v in cflags.values()) > sum(int(v) for v in rflags.values()):
            blocked.append('challenger_higher_error_flags')
        elif (cur and cur.get('source_family_count',0) >= chal.get('source_family_count',0)):
            blocked.append('current_source_family_not_weaker')
        else:
            chosen=sup
    return chosen, {'override': chosen!=current_answer, 'blocked_conditions': blocked, 'reasons':[f'support_challenger={sup}']}
