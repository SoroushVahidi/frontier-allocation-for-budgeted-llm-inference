#!/usr/bin/env python3
"""
Full learned_router_v2 training and comprehensive evaluation.

Implements all evaluation protocols:
- Within-scenario CV
- Pooled stratified CV  
- Leave-one-scenario-out
- Provider heldout
- Dataset heldout
"""

import os
import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import pickle

import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import StratifiedKFold, cross_val_predict, LeaveOneGroupOut
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, roc_curve, auc
from sklearn.calibration import CalibratedClassifierCV
from joblib import dump, load

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_official_case_table(path: str) -> pd.DataFrame:
    """Load official case table with action labels."""
    df = pd.read_csv(path)
    logger.info(f"Loaded official case table: {len(df)} rows")
    return df


def load_rg_eb_feature_table(path: str) -> pd.DataFrame:
    """Load RG-EB feature table with runtime-legal features."""
    df = pd.read_csv(path)
    logger.info(f"Loaded RG-EB feature table: {len(df)} rows")
    return df


def prepare_datasets(case_table: pd.DataFrame, feature_table: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
    """Prepare official training table with features and labels."""
    
    merged = pd.merge(
        case_table,
        feature_table,
        left_on='example_id',
        right_on='example_id',
        how='inner',
        suffixes=('', '_feat')
    )
    
    logger.info(f"After merge: {len(merged)} rows")
    
    action_col_map = {
        'pooled4_correct': 'pooled4_ok',
        'agreement_only_correct': 'agreement_only_ok',
        'beta_shrinkage_correct': 'beta_shrinkage_ok',
        'C1d_correct': 'c1d_ok',
        'C1a_t005_correct': 'c1a_t005_ok',
        'frontier_correct': 'frontier_ok',
        'L1_correct': 'L1_ok',
        'S1_correct': 'S1_ok',
        'TALE_correct': 'TALE_ok',
    }
    
    action_labels = {}
    for target_col, source_col in action_col_map.items():
        if source_col in merged.columns:
            action_labels[target_col] = merged[source_col].fillna(0).astype(int).values
    
    logger.info(f"Prepared {len(merged)} examples with {len(action_labels)} action labels")
    return merged, action_labels


def get_numeric_features(df: pd.DataFrame) -> List[str]:
    """Get numeric features for scaling (excluding oracle/gold-derived columns)."""
    
    # Columns to exclude (oracle labels and answer columns)
    exclude_patterns = [
        '_ok', '_failed', '_ans', '_decision', 'oracle', 'gold',
        'pooled4', 'agreement_only', 'beta_shrinkage', 'c1d', 'c1a_t005', 'always_s1',
        'frontier_correct', 'L1_correct', 'S1_correct', 'TALE_correct'
    ]
    
    # Columns to always exclude by name
    exclude_exact = {
        'example_id', 'question', 'gold', 'scenario_id', 'provider', 'dataset',
        'unique_answer_count_feat', 'n_valid_sources'
    }
    
    numeric_cols = []
    for col in df.columns:
        # Skip excluded names
        if col in exclude_exact:
            continue
        
        # Skip if matches any exclude pattern
        if any(pattern in col.lower() for pattern in exclude_patterns):
            continue
        
        # Include only numeric columns
        if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
            numeric_cols.append(col)
    
    return numeric_cols


def train_action_model(X_train: np.ndarray, y_train: np.ndarray, model_type: str = 'hgb') -> Any:
    """Train binary action model."""
    
    if model_type == 'logistic':
        model = LogisticRegression(random_state=42, max_iter=1000, n_jobs=-1)
    elif model_type == 'rf':
        model = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=15, n_jobs=-1)
    elif model_type == 'hgb':
        model = HistGradientBoostingClassifier(random_state=42, max_iter=100, max_depth=5)
    elif model_type == 'lgb' and HAS_LIGHTGBM:
        model = lgb.LGBMClassifier(random_state=42, n_estimators=100, max_depth=5)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    model.fit(X_train, y_train)
    return model


def eval_action_correctness(y_true, y_pred) -> Dict[str, float]:
    """Evaluate single action model."""
    return {
        'accuracy': accuracy_score(y_true, y_pred),
        'precision': precision_score(y_true, y_pred, zero_division=0),
        'recall': recall_score(y_true, y_pred, zero_division=0),
        'f1': f1_score(y_true, y_pred, zero_division=0),
    }


def evaluate_within_scenario_cv(df: pd.DataFrame, X: np.ndarray, action_labels: Dict, output_root: str):
    """5-fold CV within each scenario."""
    
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
            'min_accuracy': np.min(fold_accs),
            'max_accuracy': np.max(fold_accs),
        })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'router_v2_within_scenario_cv_summary.csv'), index=False)
    logger.info(f"Within-scenario CV: mean={results_df['mean_accuracy'].mean():.4f}")
    return results_df


def evaluate_pooled_cv(df: pd.DataFrame, X: np.ndarray, action_labels: Dict, output_root: str):
    """Pooled stratified 5-fold CV across all scenarios."""
    
    results = {'variant': 'pooled_cv_hgb'}
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
    results_df.to_csv(os.path.join(output_root, 'router_v2_official_pooled_cv_summary.csv'), index=False)
    logger.info(f"Pooled CV: accuracy={results['mean_accuracy']:.4f} ± {results['std_accuracy']:.4f}")
    return results_df


def evaluate_loso(df: pd.DataFrame, X: np.ndarray, action_labels: Dict, output_root: str):
    """Leave-one-scenario-out evaluation."""
    
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
        
        results.append({
            'held_out_scenario': test_scenario,
            'accuracy': acc
        })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'router_v2_leave_one_scenario_out_summary.csv'), index=False)
    logger.info(f"LOSO: mean={results_df['accuracy'].mean():.4f}, worst={results_df['accuracy'].min():.4f}")
    return results_df


def evaluate_provider_heldout(df: pd.DataFrame, X: np.ndarray, action_labels: Dict, output_root: str):
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
            
            results.append({
                'train_provider': train_provider,
                'test_provider': test_provider,
                'accuracy': acc
            })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'router_v2_provider_heldout_summary.csv'), index=False)
    logger.info(f"Provider heldout: mean={results_df['accuracy'].mean():.4f}")
    return results_df


def evaluate_dataset_heldout(df: pd.DataFrame, X: np.ndarray, action_labels: Dict, output_root: str):
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
            
            results.append({
                'train_dataset': train_dataset,
                'test_dataset': test_dataset,
                'accuracy': acc
            })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(os.path.join(output_root, 'router_v2_dataset_heldout_summary.csv'), index=False)
    logger.info(f"Dataset heldout: mean={results_df['accuracy'].mean():.4f}")
    return results_df


def main():
    parser = argparse.ArgumentParser(description="Train and evaluate learned_router_v2 (full)")
    parser.add_argument('--output-root', default='outputs/learned_router_v2_20260524', help='Output root')
    args = parser.parse_args()
    
    output_root = args.output_root
    os.makedirs(output_root, exist_ok=True)
    
    log_file = os.path.join(output_root, f'full_train_{datetime.now().strftime("%Y%m%dT%H%M%SZ")}.log')
    fh = logging.FileHandler(log_file)
    logger.addHandler(fh)
    
    logger.info("Starting full learned_router_v2 training")
    
    try:
        # Load data
        case_table = load_official_case_table('outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv')
        feature_table = load_rg_eb_feature_table('outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv')
        
        # Prepare merged dataset
        df_merged, action_labels = prepare_datasets(case_table, feature_table)
        
        # Get numeric features and scale
        numeric_features = get_numeric_features(df_merged)
        logger.info(f"Using {len(numeric_features)} numeric features")
        
        X_data = df_merged[numeric_features].fillna(0).values
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_data)
        
        # Run all evaluations
        logger.info("Running within-scenario CV...")
        within_scenario = evaluate_within_scenario_cv(df_merged, X_scaled, action_labels, output_root)
        
        logger.info("Running pooled stratified CV...")
        pooled_cv = evaluate_pooled_cv(df_merged, X_scaled, action_labels, output_root)
        
        logger.info("Running leave-one-scenario-out...")
        loso = evaluate_loso(df_merged, X_scaled, action_labels, output_root)
        
        logger.info("Running provider heldout...")
        provider_heldout = evaluate_provider_heldout(df_merged, X_scaled, action_labels, output_root)
        
        logger.info("Running dataset heldout...")
        dataset_heldout = evaluate_dataset_heldout(df_merged, X_scaled, action_labels, output_root)
        
        # Save artifacts
        dump(scaler, os.path.join(output_root, 'feature_scaler_full.pkl'))
        with open(os.path.join(output_root, 'feature_schema_full.json'), 'w') as f:
            json.dump({'features': numeric_features}, f, indent=2)
        
        logger.info(f"Full training completed. Results saved to {output_root}")
        return 0
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
