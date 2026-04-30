from experiments.controllers import DirectReserveFrontierGateV2L1DirectInjectionV1Controller, DirectReserveFrontierGateV2Controller, MethodResult

class G:
    def init_branch(self, bid):
        class B: pass
        b=B(); b.branch_id=bid; b.predicted_answer=None
        return b
    def expand(self, branch, q, g): branch.predicted_answer='10'

class S: ...

def _base_run(self, q, g):
    return MethodResult(method='direct_reserve_frontier_gate_v2',prediction='7',is_correct=False,actions_used=2,expansions=2,verifications=0,avg_surviving_branches=1.0,budget_exhausted=False,metadata={'selector_candidate_pool':[{'predicted_answer':'7','source_family':'direct_reserve'}]})

def test_injection_adds_group_and_metadata(monkeypatch):
    monkeypatch.setattr(DirectReserveFrontierGateV2Controller,'run',_base_run)
    c=DirectReserveFrontierGateV2L1DirectInjectionV1Controller(G(),S(),4,enable_injection=True,strict_controller_factory=lambda _: None)
    r=c.run('q','10')
    md=r.metadata['l1_direct_injection']
    assert md['enabled'] and md['executed'] and md['formed_new_group']
    assert md['normalized_injected_answer']=='10'
    assert md['source_label']=='l1_direct_injection'
    assert md['gold_match'] is True
    assert any(x.get('source_family')=='l1_direct_injection' for x in r.metadata['selector_candidate_pool'])

def test_injection_disabled_keeps_default(monkeypatch):
    monkeypatch.setattr(DirectReserveFrontierGateV2Controller,'run',_base_run)
    c=DirectReserveFrontierGateV2L1DirectInjectionV1Controller(G(),S(),4,enable_injection=False,strict_controller_factory=lambda _: None)
    r=c.run('q','10')
    assert r.prediction=='7'
    assert r.metadata['l1_direct_injection']['enabled'] is False
