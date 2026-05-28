#!/usr/bin/env python3
"""
Train and evaluate learned_router_v2 using RG-EB action set and feature schema.

Implements action-level learned router for fixed-pool answer selection.
Strict offline evaluation with auxiliary data separation.
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
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import StratifiedKFold, cross_validate, cross_val_predict
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score
from sklearn.calibration import CalibratedClassifierCV
from joblib import dump, load

try:
    import lightgbm as lgb
    HAS_LIGHTGBM = True
except ImportError:
    HAS_LIGHTGBM = False

try:
    import xgboost as xgb
    HAS_XGBOOST = True
except ImportError:
    HAS_XGBOOST = False

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


def load_mistral_auxiliary_table(path: str) -> pd.DataFrame:
    """Load Mistral auxiliary training table."""
    df = pd.read_csv(path)
    logger.info(f"Loaded Mistral auxiliary table: {len(df)} rows")
    return df


def build_action_labels(case_table: pd.DataFrame) -> Dict[str, np.ndarray]:
    """Extract action correctness labels from case table."""
    
    action_columns = {
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
    
    labels = {}
    for target_col, source_col in action_columns.items():
        if source_col in case_table.columns:
            labels[target_col] = case_table[source_col].fillna(0).astype(int).values
    
    logger.info(f"Built action labels: {list(labels.keys())}")
    return labels


def get_runtime_legal_features(feature_table: pd.DataFrame, numeric_only: bool = True) -> List[str]:
    """Get list of runtime-legal features (no gold/oracle)."""
    
    feature_groups = {
        'agreement_numeric': [
            'unique_answer_count', 'majority_size', 
            'strict_majority_exists', 'all_four_agree', 'all_different',
            'two_two_split', 'three_one_split', 'external_majority_exists',
            'external_majority_excludes_frontier', 'external_majority_excludes_S1',
            'L1_TALE_agree', 'S1_isolated', 'S1_in_majority', 
            'frontier_in_majority', 'frontier_isolated'
        ],
        'agreement_categorical': [
            'agreement_pattern'
        ],
        'problem_bucket': [
            'question_length_bucket', 'number_count_bucket', 'difficulty_proxy',
            'has_fraction', 'has_equation'
        ],
        'calibration_bucket': [
            'calib_regime_type', 'best_calibrated_source', 'best_minus_second_spread_bucket',
            'S1_minus_second_spread_bucket', 'source_accuracy_entropy_bucket', 'majority_shape'
        ],
        'metadata': ['provider', 'dataset']
    }
    
    all_features = []
    for group_features in feature_groups.values():
        for feat in group_features:
            if feat in feature_table.columns:
                all_features.append(feat)
    
    # Filter to numeric features only (for scaling)
    if numeric_only:
        numeric_features = []
        for feat in all_features:
            if feature_table[feat].dtype in ['int64', 'float64', 'int32', 'float32']:
                numeric_features.append(feat)
        return numeric_features
    
    return all_features


def prepare_datasets(
    case_table: pd.DataFrame,
    feature_table: pd.DataFrame,
    mistral_aux_table: Optional[pd.DataFrame] = None,
    include_metadata: bool = False
) -> Tuple[pd.DataFrame, Dict[str, np.ndarray], pd.DataFrame, pd.DataFrame]:
    """Prepare official training/official aux tables."""
    
    # Merge case table with features, keeping all columns from case table
    merged = pd.merge(
        case_table,
        feature_table,
        left_on='example_id',
        right_on='example_id',
        how='inner',
        suffixes=('', '_feat')
    )
    
    logger.info(f"After merge: {len(merged)} rows")
    
    # Build action labels (from case_table columns)
    case_table_labels = {}
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
    
    for target_col, source_col in action_col_map.items():
        if source_col in merged.columns:
            case_table_labels[target_col] = merged[source_col].fillna(0).astype(int).values
    
    logger.info(f"Prepared {len(merged)} official examples with {len(case_table_labels)} action labels")
    
    return merged, case_table_labels, None, None


def train_single_action_model(
    X_train: np.ndarray,
    y_train: np.ndarray,
    model_type: str = 'logistic',
    random_state: int = 42
) -> Any:
    """Train single binary action model."""
    
    if model_type == 'logistic':
        model = LogisticRegression(
            random_state=random_state,
            max_iter=1000,
            solver='lbfgs',
            n_jobs=-1
        )
    elif model_type == 'rf':
        model = RandomForestClassifier(
            n_estimators=100,
            random_state=random_state,
            n_jobs=-1,
            max_depth=15
        )
    elif model_type == 'hgb':
        model = HistGradientBoostingClassifier(
            random_state=random_state,
            max_iter=100,
            max_depth=5
        )
    elif model_type == 'lgb' and HAS_LIGHTGBM:
        model = lgb.LGBMClassifier(
            random_state=random_state,
            n_estimators=100,
            max_depth=5,
            n_jobs=-1
        )
    else:
        raise ValueError(f"Unknown model type: {model_type}")
    
    model.fit(X_train, y_train)
    return model


def evaluate_within_scenario_cv(
    official_df: pd.DataFrame,
    X_features: pd.DataFrame,
    action_labels: Dict[str, np.ndarray],
    output_root: str,
    n_splits: int = 5
) -> pd.DataFrame:
    """Run within-scenario 5-fold CV."""
    
    results = []
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    
    for scenario in official_df['scenario_id'].unique():
        scenario_mask = official_df['scenario_id'] == scenario
        X_scenario = X_features[scenario_mask].values
        
        # Use first action as stratification target
        first_action_key = list(action_labels.keys())[0]
        y_scenario = action_labels[first_action_key][scenario_mask]
        
        fold_results = {'scenario': scenario}
        
        for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X_scenario, y_scenario)):
            X_train = X_scenario[train_idx]
            X_test = X_scenario[test_idx]
            
            fold_accs = []
            for action_name, y_full in action_labels.items():
                y_scenario_action = y_full[scenario_mask]
                y_train = y_scenario_action[train_idx]
                y_test = y_scenario_action[test_idx]
                
                model = train_single_action_model(X_train, y_train, 'hgb')
                y_pred = model.predict(X_test)
                acc = accuracy_score(y_test, y_pred)
                fold_accs.append(acc)
            
            fold_results[f'fold_{fold_idx}_mean_acc'] = np.mean(fold_accs)
        
        results.append(fold_results)
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(
        os.path.join(output_root, 'router_v2_within_scenario_cv_summary.csv'),
        index=False
    )
    logger.info(f"Within-scenario CV results saved")
    
    return results_df


def evaluate_provider_heldout(
    official_df: pd.DataFrame,
    X_features: pd.DataFrame,
    action_labels: Dict[str, np.ndarray],
    output_root: str
) -> pd.DataFrame:
    """Evaluate provider heldout: train on one provider, test on another."""
    
    results = []
    providers = official_df['provider'].unique()
    
    for train_provider in providers:
        for test_provider in providers:
            if train_provider == test_provider:
                continue
            
            train_mask = official_df['provider'] == train_provider
            test_mask = official_df['provider'] == test_provider
            
            X_train = X_features[train_mask].values
            X_test = X_features[test_mask].values
            
            first_action_key = list(action_labels.keys())[0]
            y_train_action = action_labels[first_action_key][train_mask]
            y_test_action = action_labels[first_action_key][test_mask]
            
            model = train_single_action_model(X_train, y_train_action, 'hgb')
            y_pred = model.predict(X_test)
            
            acc = accuracy_score(y_test_action, y_pred)
            results.append({
                'train_provider': train_provider,
                'test_provider': test_provider,
                'accuracy': acc
            })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(
        os.path.join(output_root, 'router_v2_provider_heldout_summary.csv'),
        index=False
    )
    logger.info("Provider heldout evaluation saved")
    
    return results_df


def evaluate_dataset_heldout(
    official_df: pd.DataFrame,
    X_features: pd.DataFrame,
    action_labels: Dict[str, np.ndarray],
    output_root: str
) -> pd.DataFrame:
    """Evaluate dataset heldout: train on one dataset, test on another."""
    
    results = []
    datasets = official_df['dataset'].unique()
    
    for train_dataset in datasets:
        for test_dataset in datasets:
            if train_dataset == test_dataset:
                continue
            
            train_mask = official_df['dataset'] == train_dataset
            test_mask = official_df['dataset'] == test_dataset
            
            X_train = X_features[train_mask].values
            X_test = X_features[test_mask].values
            
            first_action_key = list(action_labels.keys())[0]
            y_train_action = action_labels[first_action_key][train_mask]
            y_test_action = action_labels[first_action_key][test_mask]
            
            model = train_single_action_model(X_train, y_train_action, 'hgb')
            y_pred = model.predict(X_test)
            
            acc = accuracy_score(y_test_action, y_pred)
            results.append({
                'train_dataset': train_dataset,
                'test_dataset': test_dataset,
                'accuracy': acc
            })
    
    results_df = pd.DataFrame(results)
    results_df.to_csv(
        os.path.join(output_root, 'router_v2_dataset_heldout_summary.csv'),
        index=False
    )
    logger.info("Dataset heldout evaluation saved")
    
    return results_df


def main():
    parser = argparse.ArgumentParser(
        description="Train and evaluate learned_router_v2"
    )
    parser.add_argument('--output-root', default='outputs/learned_router_v2_20260524',
                       help='Output root directory')
    parser.add_argument('--full-eval', action='store_true',
                       help='Run full evaluation (slower)')
    parser.add_argument('--include-metadata', action='store_true',
                       help='Include provider/dataset metadata in features')
    parser.add_argument('--use-auxiliary', action='store_true',
                       help='Include auxiliary training data')
    
    args = parser.parse_args()
    
    output_root = args.output_root
    os.makedirs(output_root, exist_ok=True)
    
    # Setup logging
    log_file = os.path.join(output_root, f'train_log_{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}.log')
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    logger.addHandler(fh)
    
    logger.info(f"Starting learned_router_v2 training")
    logger.info(f"Output root: {output_root}")
    
    try:
        # Load data
        official_case_table = load_official_case_table(
            'outputs/rg_eb_action_router_20260524/rg_eb_official4_case_table.csv'
        )
        official_feature_table = load_rg_eb_feature_table(
            'outputs/rg_eb_action_router_20260524/rg_eb_feature_table_official4.csv'
        )
        
        # Prepare datasets
        official_df, action_labels, _, _ = prepare_datasets(
            official_case_table,
            official_feature_table,
            include_metadata=args.include_metadata
        )
        
        # Get features
        feature_cols = get_runtime_legal_features(official_feature_table, numeric_only=True)
        if not args.include_metadata:
            feature_cols = [f for f in feature_cols if f not in ['provider', 'dataset']]
        
        logger.info(f"Using {len(feature_cols)} numeric features")
        
        # Handle missing features gracefully
        available_features = [f for f in feature_cols if f in official_df.columns]
        logger.info(f"Available features: {len(available_features)}/{len(feature_cols)}")
        
        X_features = official_df[available_features].fillna(0)
        
        # Scale features
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X_features)
        X_features_scaled = pd.DataFrame(X_scaled, columns=available_features)
        
        # Run evaluations
        logger.info("Starting within-scenario CV evaluation...")
        cv_results = evaluate_within_scenario_cv(
            official_df, X_features_scaled, action_labels, output_root
        )
        
        logger.info("Starting provider heldout evaluation...")
        provider_results = evaluate_provider_heldout(
            official_df, X_features_scaled, action_labels, output_root
        )
        
        logger.info("Starting dataset heldout evaluation...")
        dataset_results = evaluate_dataset_heldout(
            official_df, X_features_scaled, action_labels, output_root
        )
        
        # Save artifacts
        dump(scaler, os.path.join(output_root, 'feature_scaler.pkl'))
        
        with open(os.path.join(output_root, 'feature_schema.json'), 'w') as f:
            json.dump({'features': feature_cols}, f, indent=2)
        
        # Summary
        logger.info(f"Training completed successfully")
        logger.info(f"Output files saved to {output_root}")
        
        return 0
        
    except Exception as e:
        logger.error(f"Training failed: {str(e)}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
