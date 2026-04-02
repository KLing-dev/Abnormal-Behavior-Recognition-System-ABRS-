from ultralytics import YOLO
import os


def download_yolov12_models():
    models = {
        "yolov8n": "yolov8n.pt",
        "yolov8s": "yolov8s.pt",
        "yolov12n": "yolov12n.pt",
    }

    weights_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "weights")
    os.makedirs(weights_dir, exist_ok=True)

    for model_name, file_name in models.items():
        model_path = os.path.join(weights_dir, file_name)
        if not os.path.exists(model_path):
            print(f"Downloading {model_name}...")
            model = YOLO(f"{model_name}.pt")
            model.save(model_path)
            print(f"Saved to {model_path}")
        else:
            print(f"{file_name} already exists")


if __name__ == "__main__":
    download_yolov12_models()
