#!/usr/bin/env python3
"""
CORRECTED: learned_router_v2 training WITHOUT leakage.

Excludes all oracle/gold-derived columns:
- all_sources_correct
- all_sources_wrong
- only_L1_correct
- only_S1_correct
- (and _ok, _failed, _ans columns from sources)

Uses ONLY legitimate runtime-legal features:
- agreement patterns (unique_answer_count, majority_size, etc.)
- question characteristics (length, number_count, has_fraction, has_equation)
- no correctness indicators
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score
from joblib import dump

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# WHITELIST of runtime-legal features ONLY
# These must NOT include any correctness, oracle, or gold-derived columns
RUNTIME_LEGAL_FEATURES = [
    # Agreement patterns (no correctness encoding)
    'unique_answer_count',
    'majority_size',
    'has_majority',
    'strict_majority_exists',
    'all_four_agree',
    'all_different',
    'two_two_split',
    'three_one_split',
    'frontier_in_majority',
    'S1_in_majority',
    'S1_isolated',
    'frontier_isolated',
    'L1_TALE_agree',
    'external_majority_exists',
    'external_majority_size',
    'external_majority_excludes_frontier',
    'external_majority_excludes_S1',
    'no_majority_flag',
    
    # Question characteristics (numeric only, exclude bucket columns)
    'question_length',
    'question_number_count',
    'question_has_equation_flag',
    'has_fraction',
    'has_equation',
]

# Columns to EXPLICITLY EXCLUDE (oracle/gold-derived)
EXCLUDED_COLUMNS = {
    # Source correctness labels
    'frontier_ok', 'frontier_failed', 'frontier_ans',
    'L1_ok', 'L1_failed', 'L1_ans',
    'S1_ok', 'S1_failed', 'S1_ans',
    'TALE_ok', 'TALE_failed', 'TALE_ans',
    
    # Action correctness labels
    'pooled4_ok', 'pooled4_decision',
    'agreement_only_ok', 'agreement_only_decision',
    'beta_shrinkage_ok', 'beta_shrinkage_decision',
    'c1d_ok', 'c1d_decision',
    'c1a_t005_ok', 'c1a_t005_decision',
    'always_s1_ok', 'always_s1_decision',
    'oracle_best_action_ok', 'oracle_best_action_decision',
    'oracle_best_source_ok',
    
    # Oracle correctness indicators (SMOKING GUN OF LEAKAGE)
    'all_sources_correct',
    'all_sources_wrong',
    'only_frontier_correct',
    'only_L1_correct',
    'only_S1_correct',
    
    # Metadata (for provider-free variant)
    'provider',
    'dataset',
    'source_split',
    'agreement_pattern',
    
    # Non-features
    'example_id',
    'question',
    'gold',
    'scenario_id',
    'n_valid_sources',
    'majority_answer',
    'external_majority_answer',
}


def get_legal_features(df: pd.DataFrame) -> list:
    """Get runtime-legal features from dataframe."""
    legal = []
    for feat in RUNTIME_LEGAL_FEATURES:
        if feat in df.columns:
            legal.append(feat)
    
    # Double-check no leaky columns snuck in
    for feat in legal:
        assert feat not in EXCLUDED_COLUMNS, f"Feature {feat} is in exclusion list!"
        # Be specific: check for actual oracle patterns
        if any(x in feat.lower() for x in ['_ok', '_failed', '_correct', 'oracle', 'only_', 'all_sources']):
            raise ValueError(f"Feature {feat} appears leaky!")
    
    return legal


def train_action_model(X_train: np.ndarray, y_train: np.ndarray, model_type: str = 'hgb'):
    """Train binary action model."""
    if model_type == 'hgb':
        model = HistGradientBoostingClassifier(random_state=42, max_iter=100, max_depth=5)
    elif model_type == 'rf':
        model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=15, n_jobs=-1)
    else:
        model = LogisticRegression(random_state=42, max_iter=1000, n_jobs=-1)
    
    model.fit(X_train, y_train)
    return model


def evaluate_within_scenario_cv(df: pd.DataFrame, X: np.ndarray, action_labels: dict, output_root: str):
    """Within-scenario 5-fold CV."""
    results = []
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    for scenario in sorted(df['scenario_id'].unique()):
        scenario_mask = (df['scenario_id'] == scenario).values
        X_scen = X[scenario_mask]
        
        first_action = list(action_labels.keys())[0]
        y_scen = action_labels[first_action][scenario_mask]
        
        fold_accs = []
        for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_scen, y_scen)):
            X_train, X_test = X_scen[train_idx], X_scen[test_idx]
            
            fold_acc_vals = []
            for action_name, y_full in action_labels.items():
                y_scen_action = y_full[scenario_mask]
                y_train = y_scen_action[train_idx]
                y_test = y_scen_action[test_idx]
                
                model = train_action_model(X_train, y_train, 'hgb')
                y_pred = model.predict(X_test)
                acc = accuracy_score(y_test, y_pred)
                fold_acc_vals.append(acc)
            
            fold_accs.append(np.mean(fold_acc_vals))
        
        results.append({
            'scenario': scenario,
            'mean_accuracy': np.mean(fold_accs),
            'std_accuracy': np.std(fold_accs),
        })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'no_leakage_within_scenario_cv.csv'), index=False)
    logger.info(f"Within-scenario CV: mean={results_df['mean_accuracy'].mean():.4f}")
    return results_df


def evaluate_pooled_cv(df: pd.DataFrame, X: np.ndarray, action_labels: dict, output_root: str):
    """Pooled stratified 5-fold CV."""
    results = {'variant': 'pooled_cv_no_leakage'}
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    first_action = list(action_labels.keys())[0]
    y = action_labels[first_action]
    
    fold_accs = []
    for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
        X_train, X_test = X[train_idx], X[test_idx]
        
        fold_acc_vals = []
        for action_name, y_full in action_labels.items():
            y_train = y_full[train_idx]
            y_test = y_full[test_idx]
            
            model = train_action_model(X_train, y_train, 'hgb')
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            fold_acc_vals.append(acc)
        
        fold_accs.append(np.mean(fold_acc_vals))
    
    results['mean_accuracy'] = np.mean(fold_accs)
    results['std_accuracy'] = np.std(fold_accs)
    results_df = pd.DataFrame([results])
    results_df.to_csv(os.path.join(output_root, 'no_leakage_pooled_cv.csv'), index=False)
    logger.info(f"Pooled CV (no leakage): accuracy={results['mean_accuracy']:.4f} ± {results['std_accuracy']:.4f}")
    return results_df


def evaluate_loso(df: pd.DataFrame, X: np.ndarray, action_labels: dict, output_root: str):
    """Leave-one-scenario-out."""
    results = []
    scenarios = sorted(df['scenario_id'].unique())
    
    for test_scenario in scenarios:
        train_mask = (df['scenario_id'] != test_scenario).values
        test_mask = (df['scenario_id'] == test_scenario).values
        
        X_train, X_test = X[train_mask], X[test_mask]
        
        first_action = list(action_labels.keys())[0]
        y_train_action = action_labels[first_action][train_mask]
        y_test_action = action_labels[first_action][test_mask]
        
        model = train_action_model(X_train, y_train_action, 'hgb')
        y_pred = model.predict(X_test)
        acc = accuracy_score(y_test_action, y_pred)
        
        results.append({'held_out_scenario': test_scenario, 'accuracy': acc})
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'no_leakage_loso.csv'), index=False)
    logger.info(f"LOSO (no leakage): mean={results_df['accuracy'].mean():.4f}")
    return results_df


def evaluate_provider_heldout(df: pd.DataFrame, X: np.ndarray, action_labels: dict, output_root: str):
    """Provider heldout evaluation."""
    results = []
    providers = sorted(df['provider'].unique())
    
    for train_provider in providers:
        for test_provider in providers:
            if train_provider == test_provider:
                continue
            
            train_mask = (df['provider'] == train_provider).values
            test_mask = (df['provider'] == test_provider).values
            
            X_train, X_test = X[train_mask], X[test_mask]
            
            first_action = list(action_labels.keys())[0]
            y_train = action_labels[first_action][train_mask]
            y_test = action_labels[first_action][test_mask]
            
            model = train_action_model(X_train, y_train, 'hgb')
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            
            results.append({'train_provider': train_provider, 'test_provider': test_provider, 'accuracy': acc})
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'no_leakage_provider_heldout.csv'), index=False)
    logger.info(f"Provider heldout (no leakage): mean={results_df['accuracy'].mean():.4f}")
    return results_df


def evaluate_dataset_heldout(df: pd.DataFrame, X: np.ndarray, action_labels: dict, output_root: str):
    """Dataset heldout evaluation."""
    results = []
    datasets = sorted(df['dataset'].unique())
    
    for train_dataset in datasets:
        for test_dataset in datasets:
            if train_dataset == test_dataset:
                continue
            
            train_mask = (df['dataset'] == train_dataset).values
            test_mask = (df['dataset'] == test_dataset).values
            
            X_train, X_test = X[train_mask], X[test_mask]
            
            first_action = list(action_labels.keys())[0]
            y_train = action_labels[first_action][train_mask]
            y_test = action_labels[first_action][test_mask]
            
            model = train_action_model(X_train, y_train, 'hgb')
            y_pred = model.predict(X_test)
            acc = accuracy_score(y_test, y_pred)
            
            results.append({'train_dataset': train_dataset, 'test_dataset': test_dataset, 'accuracy': acc})
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'no_leakage_dataset_heldout.csv'), index=False)
    logger.info(f"Dataset heldout (no leakage): mean={results_df['accuracy'].mean():.4f}")
    return results_df


def main():
    output_root = 'outputs/learned_router_v2_leakage_audit_20260524'
    os.makedirs(output_root, exist_ok=True)
    
    log_file = os.path.join(output_root, f'corrected_training_{datetime.now().strftime("%Y%m%dT%H%M%SZ")}.log')
    fh = logging.FileHandler(log_file)
    logger.addHandler(fh)
    
    logger.info("="*80)
    logger.info("CORRECTED learned_router_v2 WITHOUT LEAKAGE")
    logger.info("="*80)
    logger.info(f"Using {len(RUNTIME_LEGAL_FEATURES)} runtime-legal features")
    logger.info(f"Excluding {len(EXCLUDED_COLUMNS)} leaky/oracle/gold columns")
    
    try:
        # Load data
        case_table = pd.read_csv('outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv')
        feature_table = pd.read_csv('outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv')
        
        # Merge
        merged = pd.merge(case_table, feature_table, left_on='example_id', right_on='example_id',
                         how='inner', suffixes=('', '_feat'))
        
        logger.info(f"Merged data: {len(merged)} rows, {len(merged.columns)} columns")
        
        # Build action labels (safe - these are separate from features)
        action_labels = {}
        for action_col, label_col in [
            ('pooled4_correct', 'pooled4_ok'),
            ('frontier_correct', 'frontier_ok'),
            ('L1_correct', 'L1_ok'),
            ('S1_correct', 'S1_ok'),
            ('TALE_correct', 'TALE_ok'),
        ]:
            if label_col in merged.columns:
                action_labels[action_col] = merged[label_col].fillna(0).astype(int).values
        
        logger.info(f"Action labels: {len(action_labels)}")
        
        # Get LEGAL features only
        legal_features = get_legal_features(merged)
        logger.info(f"Legal features selected: {len(legal_features)}")
        logger.info(f"Features: {sorted(legal_features)}")
        
        # Check for any leakage
        for feat in legal_features:
            if feat in EXCLUDED_COLUMNS:
                raise ValueError(f"SAFETY CHECK FAILED: {feat} is in exclusion list!")
        
        logger.info("✓ Safety check passed: no excluded columns in feature set")
        
        # Scale features
        X_data = merged[legal_features].fillna(0).values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_data)
        
        # Run evaluations
        logger.info("\nRunning evaluations...")
        within_scenario = evaluate_within_scenario_cv(merged, X_scaled, action_labels, output_root)
        pooled_cv = evaluate_pooled_cv(merged, X_scaled, action_labels, output_root)
        loso = evaluate_loso(merged, X_scaled, action_labels, output_root)
        provider_heldout = evaluate_provider_heldout(merged, X_scaled, action_labels, output_root)
        dataset_heldout = evaluate_dataset_heldout(merged, X_scaled, action_labels, output_root)
        
        # Save artifacts
        dump(scaler, os.path.join(output_root, 'scaler_no_leakage.pkl'))
        with open(os.path.join(output_root, 'features_no_leakage.json'), 'w') as f:
            json.dump({'legal_features': legal_features}, f, indent=2)
        
        logger.info("\n" + "="*80)
        logger.info("CORRECTED RESULTS (NO LEAKAGE)")
        logger.info("="*80)
        logger.info(f"Pooled CV: {pooled_cv.iloc[0]['mean_accuracy']:.4f}")
        logger.info(f"Within-scenario: {within_scenario['mean_accuracy'].mean():.4f}")
        logger.info(f"LOSO: {loso['accuracy'].mean():.4f}")
        logger.info(f"Provider heldout: {provider_heldout['accuracy'].mean():.4f}")
        logger.info(f"Dataset heldout: {dataset_heldout['accuracy'].mean():.4f}")
        logger.info("="*80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
