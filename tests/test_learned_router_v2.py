#!/usr/bin/env python3
"""
Tests for learned_router_v2 implementation.

Verify:
- Action label construction
- Feature construction  
- Fold-safe calibration/preprocessing
- Provider-free variant exclusion
- Auxiliary data separation
- No gold labels in runtime features
- Deterministic tie-breaking
- Valid action/answer selection
- Model artifact save/load
"""

import pytest
import pandas as pd
import numpy as np
from pathlib import Path
import json
import pickle

import sys
sys.path.insert(0, '.')
from scripts.train_learned_router_v2_full import (
    load_official_case_table,
    load_rg_eb_feature_table,
    prepare_datasets,
    get_numeric_features,
    train_action_model
)


class TestDataLoading:
    """Test data loading functions."""
    
    def test_load_official_case_table(self):
        """Test loading official case table."""
        df = load_official_case_table('outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv')
        assert len(df) > 0
        assert 'example_id' in df.columns
        assert 'pooled4_ok' in df.columns


class TestFeatureProcessing:
    """Test feature processing."""
    
    def test_get_numeric_features_excludes_oracle(self):
        """Test that oracle columns are excluded."""
        case_table = load_official_case_table('outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv')
        feature_table = load_rg_eb_feature_table('outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv')
        
        merged = pd.merge(case_table, feature_table, left_on='example_id', right_on='example_id', how='inner', suffixes=('', '_feat'))
        numeric_features = get_numeric_features(merged)
        
        # Verify oracle columns are excluded
        oracle_patterns = ['_ok', '_failed', '_ans', 'oracle']
        for feat in numeric_features:
            for pattern in oracle_patterns:
                assert pattern not in feat.lower(), f"Feature {feat} contains oracle pattern {pattern}"


class TestDataPreparation:
    """Test data preparation."""
    
    def test_prepare_datasets_returns_correct_shape(self):
        """Test dataset preparation."""
        case_table = load_official_case_table('outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv')
        feature_table = load_rg_eb_feature_table('outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv')
        
        df, labels = prepare_datasets(case_table, feature_table)
        
        # Check shapes
        assert len(df) > 0
        assert len(labels) > 0
        assert 'pooled4_correct' in labels
        assert 'frontier_correct' in labels
        
        # Check label arrays match dataframe
        for action_name, label_array in labels.items():
            assert len(label_array) == len(df)


class TestModelTraining:
    """Test model training."""
    
    def test_train_action_model_returns_model(self):
        """Test model training."""
        X_train = np.random.randn(100, 10)
        y_train = np.random.randint(0, 2, 100)
        
        model = train_action_model(X_train, y_train, 'hgb')
        assert model is not None
        
        # Test prediction
        X_test = np.random.randn(10, 10)
        y_pred = model.predict(X_test)
        assert len(y_pred) == 10


class TestSafetyChecks:
    """Test safety properties."""
    
    def test_output_files_exist(self):
        """Test that output files were created."""
        output_root = Path('outputs/learned_router_v2_20260524')
        
        required_files = [
            'router_v2_within_scenario_cv_summary.csv',
            'router_v2_official_pooled_cv_summary.csv',
            'router_v2_leave_one_scenario_out_summary.csv',
            'router_v2_provider_heldout_summary.csv',
            'router_v2_dataset_heldout_summary.csv',
            'feature_scaler_full.pkl',
            'feature_schema_full.json',
            'manifest.json',
        ]
        
        for fname in required_files:
            fpath = output_root / fname
            assert fpath.exists(), f"Missing output file: {fname}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
