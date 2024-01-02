# -*- coding: utf-8 -*-
# ! python3

# Developed by: Alexander Kireev
# Created: 01.11.2023
# Updated: 19.12.2023
# Website: https://bespredel.name
import os
import torch
from ultralytics import YOLO

default_model_name = 'yolov8n.pt'
model_name = 'yolov8_custom'
model_task = 'detect'
mode = 'train'  # 'export' or 'train'
export_format = 'engine'  # 'engine', 'onnx', etc...

# Specify the save directory for training runs
cfg_dir = 'yolo_cfg'
os.makedirs(cfg_dir, exist_ok=True)
os.makedirs(f'{cfg_dir}/cfg', exist_ok=True)
os.makedirs(f'{cfg_dir}/datasets', exist_ok=True)
os.makedirs(f'{cfg_dir}/models', exist_ok=True)

# Load the model
model = YOLO(f'{cfg_dir}/models/{default_model_name}')  # load a pretrained model (recommended for training)

# Training
if __name__ == '__main__':
    if mode == 'train':
        model.train(
            data=f'{cfg_dir}/cfg/{model_name}.yaml',
            imgsz=640,  # (640, 480)
            epochs=5,
            # pretrained=True,
            batch=-1,
            name=f'{model_name}',
            device=torch.device('cuda' if torch.cuda.is_available() else 'cpu'),
            save_dir=cfg_dir,
            project=f'{cfg_dir}/runs/{model_task}',
        )

        if export_format != '':
            model.export(format=export_format, device=0, simplify=True)

    if mode == 'export':
        # Export
        # Load a model
        model = YOLO(f'{cfg_dir}/runs/{model_task}/{model_name}/weights/best.pt')  # load a custom trained model

        # Export the model
        model.export(format=export_format, device=0, simplify=True)
