import pytest
from collections import Counter
from typing import Any
from experiments.controllers import DirectReserveFrontierGateController, MethodResult
from experiments.frontier_max_support_tiebreak import normalize_answer_group_key

class MockGenerator:
    def __init__(self, answers=None):
        self.answers = answers or []
        self.idx = 0
    def init_branch(self, branch_id):
        class Branch:
            def __init__(self, bid):
                self.branch_id = bid
                self.predicted_answer = None
                self.is_done = False
                self.is_pruned = False
                self.trace_events = []
        return Branch(branch_id)
    def expand(self, branch, question, gold_answer):
        if self.idx < len(self.answers):
            branch.predicted_answer = self.answers[self.idx]
            branch.is_done = True
            branch.trace_events.append({"reasoning_text": f"Reasoning for {branch.predicted_answer}", "extracted_answer": branch.predicted_answer})
            self.idx += 1

class MockScorer:
    def score(self, branch, question, gold_answer):
        return 1.0

def test_direct_l1_anchor_injection():
    # Setup: 1 direct answer "10", 1 hybrid seed "20", 0 frontier expansion
    gen = MockGenerator(answers=["10", "20"])
    scorer = MockScorer()
    
    class MockFrontier:
        def run(self, q, g):
            return MethodResult(method="mock", prediction=None, is_correct=False, actions_used=0, expansions=0, verifications=0, 
                                avg_surviving_branches=1.0, budget_exhausted=False, metadata={})

    ctrl = DirectReserveFrontierGateController(
        gen, scorer, max_actions_per_problem=10,
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=True,
        direct_hybrid_seed_budget_actions=1,
        enable_frontier_max_support_tiebreak=True,
        strict_controller_factory=lambda b: MockFrontier()
    )
    
    res = ctrl.run("What is 5+5?", "10")
    md = res.metadata
    
    assert md["direct_l1_anchor_present"] is True
    assert md["direct_l1_anchor_answer"] == "20"
    assert md["direct_l1_anchor_added_to_pool"] is True
    
    pool = md["selector_candidate_pool"]
    anchor_nodes = [n for n in pool if n.get("source_id") == "direct_l1_anchor"]
    assert len(anchor_nodes) == 1
    assert anchor_nodes[0]["predicted_answer"] == "20"
    assert anchor_nodes[0]["source_metadata"] == "direct_l1_anchor"
    
    # Check support counts
    counts = md["answer_group_support_counts"]
    assert counts[normalize_answer_group_key("10")] == 1
    assert counts[normalize_answer_group_key("20")] == 1
    
    assert md["candidate_pool_answer_group_count_after_anchor"] == 2
    assert md["candidate_pool_answer_group_count_before_anchor"] == 1

def test_direct_l1_anchor_no_duplicate_group():
    # Setup: 1 direct answer "10", 1 hybrid seed "10" (same as direct)
    gen = MockGenerator(answers=["10", "10"])
    scorer = MockScorer()
    
    class MockFrontier:
        def run(self, q, g):
            return MethodResult(method="mock", prediction=None, is_correct=False, actions_used=0, expansions=0, verifications=0, 
                                avg_surviving_branches=1.0, budget_exhausted=False, metadata={})

    ctrl = DirectReserveFrontierGateController(
        gen, scorer, max_actions_per_problem=10,
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=True,
        direct_hybrid_seed_budget_actions=1,
        enable_frontier_max_support_tiebreak=True,
        strict_controller_factory=lambda b: MockFrontier()
    )
    
    res = ctrl.run("What is 5+5?", "10")
    md = res.metadata
    
    counts = md["answer_group_support_counts"]
    assert counts[normalize_answer_group_key("10")] == 2
    
    assert md["candidate_pool_answer_group_count_after_anchor"] == 1
    assert md["candidate_pool_answer_group_count_before_anchor"] == 1

def test_direct_l1_anchor_selection_win():
    gen = MockGenerator(answers=["10", "20"])
    scorer = MockScorer()
    
    class MockFrontier:
        def run(self, q, g):
            # Frontier produces "30" with support 1
            return MethodResult(method="mock", prediction="30", is_correct=False, actions_used=1, expansions=1, verifications=0, 
                                avg_surviving_branches=1.0, budget_exhausted=False,
                                metadata={"answer_group_support_counts": {normalize_answer_group_key("30"): 1}})

    ctrl = DirectReserveFrontierGateController(
        gen, scorer, max_actions_per_problem=10,
        direct_reserve_attempts_override=1,
        enable_direct_hybrid_seed=True,
        direct_hybrid_seed_budget_actions=1,
        enable_frontier_max_support_tiebreak=True,
        gate_top_support_threshold=2.0, # Force uncertainty
        strict_controller_factory=lambda b: MockFrontier()
    )
    
    res = ctrl.run("What is 5+5?", "10")
    md = res.metadata
    
    counts = md["answer_group_support_counts"]
    assert counts[normalize_answer_group_key("10")] == 1
    assert counts[normalize_answer_group_key("20")] == 1
    assert counts[normalize_answer_group_key("30")] == 1
    
    assert md["frontier_tiebreak_triggered"] is True
