"""Image quality check, ResNet18 grading and Grad-CAM explanations."""

import threading

import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageFilter
from torchvision import models, transforms

from .config import DR_CLASSES, MIN_HEIGHT, MIN_WIDTH, MODEL_PATH, REFERABLE_THRESHOLD


# =========================================================
# IMAGE QUALITY CHECK
# =========================================================

def check_image_quality(image):
    """
    Basic prototype quality check (NOT clinically validated).

    Fundus photos have a circular retina on a black background, so
    brightness and contrast are measured on non-black pixels only.
    Only severely unusable images are rejected; normal dark/orange
    APTOS-style photographs pass.
    """
    width, height = image.size
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return {"quality": "poor",
                "message": "Image resolution is too small. Please upload a "
                           "higher-resolution fundus image."}

    # Statistics on a downscaled copy: same result, much faster on 4000 px photos
    gray_image = image.convert("L")
    gray_image.thumbnail((1024, 1024))
    gray = np.asarray(gray_image, dtype=np.float32)

    retina = gray[gray > 20]
    if retina.size < gray.size * 0.20:
        return {"quality": "poor",
                "message": "A sufficiently large retinal field could not be detected."}

    brightness = retina.mean()
    contrast = retina.std()
    edges = np.asarray(gray_image.filter(ImageFilter.FIND_EDGES), dtype=np.float32)
    edges = edges[edges > 10]
    edge_mean = edges.mean() if edges.size else 0.0

    problems = []
    if brightness < 15:
        problems.append("retinal field is extremely dark")
    if brightness > 250:
        problems.append("retinal field is extremely bright")
    if contrast < 3 and edge_mean < 0.5:
        problems.append("image may contain very little visible retinal information")

    if problems:
        return {"quality": "poor",
                "message": "Image quality may be insufficient: " + "; ".join(problems) + "."}
    return {"quality": "acceptable", "message": "Image is suitable for further analysis."}


# =========================================================
# MODEL
# =========================================================

AI_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if not MODEL_PATH.exists():
    raise FileNotFoundError(f"AI model file was not found:\n{MODEL_PATH}")

ai_model = models.resnet18(weights=None)
ai_model.fc = nn.Linear(ai_model.fc.in_features, len(DR_CLASSES))
ai_model.load_state_dict(torch.load(MODEL_PATH, map_location=AI_DEVICE))
ai_model = ai_model.to(AI_DEVICE).eval()

# Grad-CAM registers hooks on the shared model, so only one request
# may run it at a time.
model_lock = threading.Lock()

# Must match train.py: Resize(224) -> ToTensor -> ImageNet mean/std
ai_transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

print("AI model loaded:", MODEL_PATH, "on", AI_DEVICE)


def analyze_image(image_path, explanation_path):
    """
    Grade one fundus image and save its Grad-CAM overlay.

    A single forward pass gives both the class probabilities and the
    activations Grad-CAM needs (final ResNet18 block). Referable DR is
    P(grade 2) + P(grade 3) + P(grade 4) >= REFERABLE_THRESHOLD.
    """
    original = Image.open(image_path).convert("RGB")
    input_tensor = ai_transform(original).unsqueeze(0).to(AI_DEVICE)

    activations, gradients = [], []
    target_layer = ai_model.layer4[-1]

    with model_lock:
        fh = target_layer.register_forward_hook(
            lambda module, inputs, output: activations.append(output))
        bh = target_layer.register_full_backward_hook(
            lambda module, grad_input, grad_output: gradients.append(grad_output[0]))
        try:
            ai_model.zero_grad(set_to_none=True)
            output = ai_model(input_tensor)
            probabilities = torch.softmax(output, dim=1)[0].detach().cpu()
            grade = int(probabilities.argmax())
            output[0, grade].backward()
            activation = activations[-1].detach()[0]
            gradient = gradients[-1].detach()[0]
        finally:
            fh.remove()
            bh.remove()
            ai_model.zero_grad(set_to_none=True)

    weights = gradient.mean(dim=(1, 2))
    cam = torch.relu((weights[:, None, None] * activation).sum(dim=0))
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)
    save_gradcam_overlay(original, cam.cpu().numpy(), explanation_path)

    referable_probability = float(probabilities[2:].sum())
    return {
        "grade": grade,
        "confidence": float(probabilities[grade]),
        "referable": referable_probability >= REFERABLE_THRESHOLD,
        "referable_probability": referable_probability,
        "probabilities": [round(float(p), 4) for p in probabilities],
    }


def save_gradcam_overlay(original, cam, output_path):
    cam_img = Image.fromarray(np.uint8(cam * 255), mode="L").resize(
        original.size, Image.Resampling.BILINEAR)
    heat = np.asarray(cam_img).astype(np.float32) / 255.0
    rgb = np.asarray(original).astype(np.float32) / 255.0

    # Simple blue -> cyan -> yellow -> red heatmap.
    heat_rgb = np.stack([
        np.clip(1.5 * heat, 0, 1),
        np.clip(1.5 * (1 - np.abs(heat - 0.5) * 2), 0, 1),
        np.clip(1.5 * (1 - heat), 0, 1),
    ], axis=2)
    alpha = (heat ** 1.2)[..., None] * 0.45
    overlay = np.clip(rgb * (1 - alpha) + heat_rgb * alpha, 0, 1)
    Image.fromarray(np.uint8(overlay * 255), mode="RGB").save(output_path, quality=92)
