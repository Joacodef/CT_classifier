import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import json
import numpy as np
from matplotlib.gridspec import GridSpec
from pathlib import Path
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


def json_serializable(obj):
    """
    Converts non-serializable objects into types that are JSON-compatible.

    This function handles common data types found in scientific computing
    libraries like NumPy and standard Python objects that `json.dump` does not
    natively support.

    Args:
        obj (Any): The object to convert.

    Returns:
        Any: A JSON-serializable representation of the object.
    """
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, tuple):
        return list(obj)
    elif isinstance(obj, Path):
        return str(obj)
    elif hasattr(obj, '__dict__'):
        return str(obj)  # For complex objects, convert to string
    else:
        return obj


def safe_json_dump(data, file_path):
    """
    Recursively converts and saves a dictionary to a JSON file.

    This function traverses a dictionary and uses `json_serializable` to ensure
    all its values are compatible with JSON before writing to a file.

    Args:
        data (Dict): The dictionary to save.
        file_path (Path): The path to the output JSON file.
    """
    def convert_item(item):
        if isinstance(item, dict):
            return {k: convert_item(v) for k, v in item.items()}
        elif isinstance(item, list):
            return [convert_item(v) for v in item]
        else:
            return json_serializable(item)
    
    converted_data = convert_item(data)
    
    with open(file_path, 'w') as f:
        json.dump(converted_data, f, indent=2)


def generate_final_report(history: dict, config, best_epoch_idx: int):
    """
    Generates a comprehensive visual report of the training process.

    This function creates a multi-panel plot summarizing the model's training
    and validation performance over epochs. It saves the report as both a PNG
    and a PDF file in the specified output directory.

    Args:
        history (Dict): A dictionary containing training history, including
                        'train_loss', 'valid_loss', and 'metrics' per epoch.
        config (Any): The configuration object containing model and training parameters.
        best_epoch_idx (int): The zero-based index of the epoch with the best
                              performance, used for highlighting.
    """
    
    logger.info("Generating final training report...")
    
    # Create figure with subplots and better spacing
    fig = plt.figure(figsize=(22, 18))  # Increased size
    gs = GridSpec(4, 3, figure=fig, hspace=0.35, wspace=0.4)  # More spacing
    
    # Extract data from history
    epochs = list(range(1, len(history['train_loss']) + 1))
    train_losses = history['train_loss']
    valid_losses = history['valid_loss']
    
    # Extract metrics over epochs
    
    # Safely extract metrics over epochs, filling missing values with None
    metrics_keys = [
        'roc_auc_macro', 'roc_auc_micro', 'f1_macro', 'f1_micro', 
        'accuracy', 'precision_macro', 'recall_macro'
    ]
    metrics_over_time = {
        key: [epoch_metrics.get(key, None) for epoch_metrics in history['metrics']]
        for key in metrics_keys
    }
    
    # 1. Training and Validation Loss
    ax1 = fig.add_subplot(gs[0, 0])
    ax1.plot(epochs, train_losses, 'b-', label='Training Loss', linewidth=2)
    ax1.plot(epochs, valid_losses, 'r-', label='Validation Loss', linewidth=2)
    ax1.set_xlabel('Epoch', fontsize=12)
    ax1.set_ylabel('Loss', fontsize=12)
    ax1.set_title('Training Progress: Loss', fontsize=14, fontweight='bold')
    
    # Mark best epoch
    ax1.axvline(x=best_epoch_idx + 1, color='green', linestyle='--', alpha=0.5, label=f'Best Epoch ({best_epoch_idx + 1})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # 2. ROC AUC Scores
    ax2 = fig.add_subplot(gs[0, 1])
    ax2.plot(epochs, metrics_over_time['roc_auc_macro'], 'g-', label='Macro AUC', linewidth=2)
    ax2.plot(epochs, metrics_over_time['roc_auc_micro'], 'orange', label='Micro AUC', linewidth=2)
    ax2.set_xlabel('Epoch', fontsize=12)
    ax2.set_ylabel('AUC Score', fontsize=12)
    ax2.set_title('ROC AUC Scores', fontsize=14, fontweight='bold')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_ylim([0, 1])
    
    # 3. F1 Scores
    ax3 = fig.add_subplot(gs[0, 2])
    ax3.plot(epochs, metrics_over_time['f1_macro'], 'purple', label='Macro F1', linewidth=2)
    ax3.plot(epochs, metrics_over_time['f1_micro'], 'brown', label='Micro F1', linewidth=2)
    ax3.set_xlabel('Epoch', fontsize=12)
    ax3.set_ylabel('F1 Score', fontsize=12)
    ax3.set_title('F1 Scores', fontsize=14, fontweight='bold')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    ax3.set_ylim([0, 1])
    
    # 4. Precision, Recall, and Accuracy
    ax4 = fig.add_subplot(gs[1, 0])
    ax4.plot(epochs, metrics_over_time['precision_macro'], 'cyan', label='Precision (Macro)', linewidth=2)
    ax4.plot(epochs, metrics_over_time['recall_macro'], 'magenta', label='Recall (Macro)', linewidth=2)
    ax4.plot(epochs, metrics_over_time['accuracy'], 'navy', label='Accuracy', linewidth=2)
    ax4.set_xlabel('Epoch', fontsize=12)
    ax4.set_ylabel('Score', fontsize=12)
    ax4.set_title('Precision, Recall & Accuracy', fontsize=14, fontweight='bold')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_ylim([0, 1])
    
    # 5. Per-Pathology AUC Heatmap (Final Epoch)
    final_metrics = history['metrics'][-1]
    pathology_aucs = {}
    for pathology in config.pathologies.columns:
        key = f"{pathology}_auc"
        if key in final_metrics:
            pathology_aucs[pathology] = final_metrics[key]
    
    if pathology_aucs:
        ax5 = fig.add_subplot(gs[1, 1:])
        pathology_names = list(pathology_aucs.keys())
        auc_values = list(pathology_aucs.values())
        
        # Shorten pathology names for better display
        short_names = []
        for name in pathology_names:
            if len(name) > 20:
                short_names.append(name[:17] + "...")
            else:
                short_names.append(name)
        
        # Create horizontal bar chart
        y_pos = np.arange(len(short_names))
        bars = ax5.barh(y_pos, auc_values, color=plt.cm.viridis(np.array(auc_values)))
        
        # Add value labels
        for i, (name, value) in enumerate(zip(short_names, auc_values)):
            ax5.text(value + 0.01, i, f'{value:.3f}', va='center', fontsize=9)
        
        ax5.set_yticks(y_pos)
        ax5.set_yticklabels(short_names, fontsize=9)
        ax5.set_xlabel('AUC Score', fontsize=12)
        ax5.set_title('Per-Pathology AUC Scores (Final Epoch)', fontsize=14, fontweight='bold')
        ax5.set_xlim([0, 1.15])  # Slightly more space for labels
        ax5.grid(True, alpha=0.3, axis='x')
        
        # Adjust layout to prevent overlap
        plt.setp(ax5.get_yticklabels(), fontsize=9)
        ax5.tick_params(axis='y', which='major', pad=5)
    
    # 6. Learning Rate Schedule (if available)
    ax6 = fig.add_subplot(gs[2, 0])
    if hasattr(config, 'training') and hasattr(config.training, 'learning_rate'):
        # Approximate cosine annealing schedule visualization
        lr_schedule = []
        initial_lr = config.training.learning_rate
        for epoch in range(len(epochs)):
            if epoch < len(epochs):
                # Cosine annealing formula
                lr = 1e-6 + (initial_lr - 1e-6) * 0.5 * (1 + np.cos(np.pi * epoch / len(epochs)))
                lr_schedule.append(lr)
        
        ax6.plot(epochs, lr_schedule, 'r-', linewidth=2)
        ax6.set_xlabel('Epoch', fontsize=12)
        ax6.set_ylabel('Learning Rate', fontsize=12)
        ax6.set_title('Learning Rate Schedule', fontsize=14, fontweight='bold')
        ax6.set_yscale('log')
        ax6.grid(True, alpha=0.3)
    
    # 7. Best Epoch Metrics Summary
    ax7 = fig.add_subplot(gs[2, 1:])
    ax7.axis('off')
    
    best_metrics = history['metrics'][best_epoch_idx]
    summary_text = f"Best Model Summary (Epoch {best_epoch_idx + 1})\n"
    summary_text += "=" * 40 + "\n\n"
    summary_text += f"Validation Loss: {valid_losses[best_epoch_idx]:.4f}\n"
    summary_text += f"ROC AUC (Macro): {best_metrics.get('roc_auc_macro', 0.0):.4f}\n"
    summary_text += f"ROC AUC (Micro): {best_metrics.get('roc_auc_micro', 0.0):.4f}\n"
    summary_text += f"F1 Score (Macro): {best_metrics.get('f1_macro', 0.0):.4f}\n"
    summary_text += f"Accuracy: {best_metrics.get('accuracy', 0.0):.4f}\n"
    summary_text += f"Precision (Macro): {best_metrics.get('precision_macro', 0.0):.4f}\n"
    summary_text += f"Recall (Macro): {best_metrics.get('recall_macro', 0.0):.4f}\n"
    
    ax7.text(0.05, 0.95, summary_text, transform=ax7.transAxes, 
             fontsize=12, verticalalignment='top', fontfamily='monospace',
             bbox=dict(boxstyle='round', facecolor='lightgray', alpha=0.5))
    
    # 8. Per-Pathology Performance Matrix (Best Epoch)
    ax8 = fig.add_subplot(gs[3, :])
    
    # Create performance matrix
    pathology_metrics = ['auc', 'f1', 'precision', 'recall', 'sensitivity', 'specificity']
    performance_matrix = []
    pathology_names_short = []
    
    for pathology in config.pathologies.columns:
        row = []
        for metric in pathology_metrics:
            key = f"{pathology}_{metric}"
            row.append(best_metrics.get(key, 0.0))
        if any(v > 0 for v in row):  # Only include pathologies with data
            performance_matrix.append(row)
            # Shorten long pathology names
            short_name = pathology[:20] + '...' if len(pathology) > 20 else pathology
            pathology_names_short.append(short_name)
    
    if performance_matrix:
        performance_matrix = np.array(performance_matrix)
        
        # Create heatmap
        im = ax8.imshow(performance_matrix, cmap='RdYlGn', aspect='auto', vmin=0, vmax=1)
        
        # Set ticks and labels
        ax8.set_xticks(np.arange(len(pathology_metrics)))
        ax8.set_yticks(np.arange(len(pathology_names_short)))
        ax8.set_xticklabels([m.capitalize() for m in pathology_metrics])
        ax8.set_yticklabels(pathology_names_short)
        
        # Rotate the tick labels for better readability
        plt.setp(ax8.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=ax8, fraction=0.046, pad=0.04)
        cbar.set_label('Score', rotation=270, labelpad=20)
        
        # Add text annotations
        for i in range(len(pathology_names_short)):
            for j in range(len(pathology_metrics)):
                text = ax8.text(j, i, f'{performance_matrix[i, j]:.2f}',
                               ha="center", va="center", color="black" if performance_matrix[i, j] > 0.5 else "white",
                               fontsize=8)
        
        ax8.set_title('Per-Pathology Performance Metrics (Best Epoch)', fontsize=14, fontweight='bold', pad=20)
    
    # Overall title
    fig.suptitle(f'CT 3D Classifier Training Report - {config.model.type}', fontsize=16, fontweight='bold')
    
    # Adjust layout to prevent title overlap and ensure all elements fit.
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    # Save the figure
    report_path = config.paths.output_dir / 'training_report.png'
    plt.savefig(report_path, dpi=300, bbox_inches='tight', facecolor='white', 
                edgecolor='none', pad_inches=0.2)
    logger.info(f"Training report saved to: {report_path}")
    
    # Also save as PDF for better quality
    report_pdf_path = config.paths.output_dir / 'training_report.pdf'
    plt.savefig(report_pdf_path, format='pdf', bbox_inches='tight', facecolor='white',
                edgecolor='none', pad_inches=0.2)
    logger.info(f"Training report (PDF) saved to: {report_pdf_path}")
    
    plt.close()
    
    # Generate additional CSV report with detailed metrics
    generate_csv_report(history, config, best_epoch_idx)


def generate_csv_report(history: dict, config, best_epoch_idx: int):
    """
    Generates detailed data files summarizing the training run.

    This function creates two files:
    1. A CSV file (`training_metrics_detailed.csv`) with per-epoch metrics.
    2. A JSON file (`training_summary.json`) with final summary statistics
       and key configuration parameters.

    Args:
        history (Dict): The training history dictionary.
        config (Any): The configuration object for the run.
        best_epoch_idx (int): The zero-based index of the best epoch.
    """
    
    # Create a detailed metrics DataFrame
    metrics_data = []
    
    for epoch, (train_loss, valid_loss, metrics) in enumerate(zip(
        history['train_loss'], 
        history['valid_loss'], 
        history['metrics']
    )):
        row = {
            'epoch': epoch + 1,
            'train_loss': float(train_loss),  # Ensure it's a regular Python float
            'valid_loss': float(valid_loss),
            'is_best': epoch == best_epoch_idx
        }
        
        # Add all metrics, converting to regular Python types
        for key, value in metrics.items():
            if isinstance(value, (np.integer, np.floating)):
                row[key] = float(value)
            else:
                row[key] = value
        
        metrics_data.append(row)
    
    # Create DataFrame and save
    metrics_df = pd.DataFrame(metrics_data)
    csv_path = config.paths.output_dir / 'training_metrics_detailed.csv'
    metrics_df.to_csv(csv_path, index=False)
    logger.info(f"Detailed metrics CSV saved to: {csv_path}")
    
    # Create summary statistics - convert everything to JSON-serializable types
    best_metrics = history['metrics'][best_epoch_idx]
    summary_stats = {
        'Total Epochs': len(history['train_loss']),
        'Best Epoch': int(best_epoch_idx + 1),
        'Best Validation Loss': float(history['valid_loss'][best_epoch_idx]),
        'Best ROC AUC (Macro)': float(best_metrics.get('roc_auc_macro', 0.0)),
        'Final Training Loss': float(history['train_loss'][-1]),
        'Final Validation Loss': float(history['valid_loss'][-1]),
        'Training Time per Epoch (avg)': 'Not tracked',
        'Model Type': str(config.model.type) if hasattr(config, 'model') else 'Unknown',
        'Number of Pathologies': len(config.pathologies.columns) if hasattr(config, 'pathologies') else 'Unknown',
        'Batch Size': int(config.training.batch_size) if hasattr(config, 'training') else 'Unknown',
        'Learning Rate': float(config.training.learning_rate) if hasattr(config, 'training') else 'Unknown',
        'Target Shape (DHW)': list(config.image_processing.target_shape_dhw) if hasattr(config, 'image_processing') else 'Unknown',
        'Target Spacing (mm)': list(config.image_processing.target_spacing) if hasattr(config, 'image_processing') else 'Unknown',
    }
    
    # Save summary using safe JSON dump
    summary_path = config.paths.output_dir / 'training_summary.json'
    safe_json_dump(summary_stats, summary_path)
    logger.info(f"Training summary saved to: {summary_path}")