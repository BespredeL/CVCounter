# -*- coding: utf-8 -*-
# ! python3

# Developed by: Aleksandr Kireev
# Created: 01.11.2023
# Updated: 03.12.2024
# Website: https://bespredel.name

import os
import torch
from ultralytics import YOLO

# Configurations
DEFAULT_MODEL_NAME = 'yolo11n.pt'
MODEL_NAME = 'yolo11_cvcounter'
MODEL_TASK = 'detect'
MODE = 'train'  # 'train' or 'export'
EXPORT_FORMAT = 'engine'  # 'engine', 'onnx', etc.
IMG_SIZE = 640  # Image size for training
EPOCHS = 100  # Number of training epochs
CFG_DIR = 'yolo_cfg'


# Check exists directories
def setup_directories():
    os.makedirs(CFG_DIR, exist_ok=True)
    os.makedirs(f'{CFG_DIR}/cfg', exist_ok=True)
    os.makedirs(f'{CFG_DIR}/datasets', exist_ok=True)
    os.makedirs(f'{CFG_DIR}/models', exist_ok=True)


# Load model
def load_model(model_path):
    try:
        return YOLO(model_path)
    except Exception as e:
        print(f"Error loading model: {e}")
        exit(1)


# Train the model
def train_model(model):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.train(
        data=f'{CFG_DIR}/cfg/{MODEL_NAME}.yaml',
        imgsz=IMG_SIZE,
        epochs=EPOCHS,
        batch=-1,
        name=MODEL_NAME,
        device=device,
        save_dir=CFG_DIR,
        project=f'{CFG_DIR}/runs/{MODEL_TASK}',
    )

    if EXPORT_FORMAT:
        model.export(format=EXPORT_FORMAT, device=0, simplify=True)


# Export the trained model
def export_model():
    model_path = f'{CFG_DIR}/runs/{MODEL_TASK}/{MODEL_NAME}/weights/best.pt'
    model = load_model(model_path)
    model.export(format=EXPORT_FORMAT, device=0, simplify=True)


# Main
if __name__ == '__main__':
    setup_directories()
    model = load_model(f'{CFG_DIR}/models/{DEFAULT_MODEL_NAME}')

    if MODE == 'train':
        train_model(model)
    elif MODE == 'export':
        export_model()
    else:
        print("Invalid mode. Use 'train' or 'export'.")
