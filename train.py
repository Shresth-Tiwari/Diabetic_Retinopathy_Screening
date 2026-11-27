import torch
import torch.nn as nn
import torch.optim as optim

import csv
import json
import time

from pathlib import Path
from PIL import Image

from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms


# Paths
BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "DataBase"
CACHE_DIR = DATA_DIR / "cache_224"

MODEL_PATH = BASE_DIR / "models" / "retinova_resnet18_new.pth"
RESULTS_DIR = BASE_DIR / "results"


# Basic settings
IMAGE_SIZE = 224
BATCH_SIZE = 32
EPOCHS = 15
LEARNING_RATE = 0.0003

CLASSES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]

MEAN = [0.485, 0.456, 0.406]
STD = [0.229, 0.224, 0.225]

THRESHOLD = 0.05


# Dataset files
FILES = {
    "train": ("train_1.csv", "train_images"),
    "val": ("valid.csv", "val_images"),
    "test": ("test.csv", "test_images")
}


# Read image names and labels from CSV
def read_data(split):
    csv_file = FILES[split][0]
    data = []
    with open(DATA_DIR / csv_file, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            image_name = row["id_code"]
            label = int(row["diagnosis"])
            data.append((image_name, label))
    return data


# Resize images and save them
def resize_images():
    for split in FILES:
        image_folder = FILES[split][1]
        output_folder = CACHE_DIR / split
        output_folder.mkdir(parents=True, exist_ok=True)
        data = read_data(split)
        for image_name, label in data:
            old_path = DATA_DIR / image_folder / (image_name + ".png")
            new_path = output_folder / (image_name + ".png")
            if not new_path.exists():
                image = Image.open(old_path).convert("RGB")
                # Bilinear, the same resize the app uses (backend/ai.py)
                image = image.resize((224, 224), Image.BILINEAR)
                image.save(new_path)
        print(split, "images ready")


# Create dataset
class RetinaDataset(Dataset):
    def __init__(self, split, transform):
        self.data = read_data(split)
        self.folder = CACHE_DIR / split
        self.transform = transform
    def __len__(self):
        return len(self.data)
    def __getitem__(self, index):
        image_name, label = self.data[index]
        image_path = self.folder / (image_name + ".png")
        image = Image.open(image_path).convert("RGB")
        image = self.transform(image)
        return image, label


# Image preprocessing
train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(180),
    transforms.ColorJitter(
        brightness=0.2,
        contrast=0.2
    ),
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD)
])

test_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(MEAN, STD)
])


# Create ResNet18 model
def create_model():
    model = models.resnet18(
        weights=models.ResNet18_Weights.IMAGENET1K_V1
    )
    # Change final layer for our 5 classes
    model.fc = nn.Linear(model.fc.in_features, 5)
    return model


# Calculate Quadratic Weighted Kappa
def calculate_kappa(actual, predicted):
    n = 5
    matrix = torch.zeros(n, n)
    for i in range(len(actual)):
        matrix[actual[i]][predicted[i]] += 1
    weights = torch.zeros(n, n)
    for i in range(n):
        for j in range(n):
            weights[i][j] = ((i - j) ** 2) / ((n - 1) ** 2)
    actual_sum = matrix.sum(dim=1)
    predicted_sum = matrix.sum(dim=0)
    expected = torch.outer(actual_sum, predicted_sum) / matrix.sum()
    kappa = 1 - (
        (weights * matrix).sum() /
        (weights * expected).sum()
    )
    return kappa.item()


# Evaluate the model
def evaluate_model(model, loader, device):
    model.eval()
    actual = []
    predicted = []
    referable_probs = []
    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            outputs = model(images)
            probabilities = torch.softmax(outputs, dim=1)
            predictions = probabilities.argmax(dim=1)
            actual.extend(labels.tolist())
            predicted.extend(predictions.cpu().tolist())
            # Classes 2, 3 and 4 are referable DR
            referable = probabilities[:, 2:].sum(dim=1)
            referable_probs.extend(referable.cpu().tolist())
    correct = 0
    for i in range(len(actual)):
        if actual[i] == predicted[i]:
            correct += 1
    accuracy = correct / len(actual)
    kappa = calculate_kappa(actual, predicted)
    return accuracy, kappa, actual, predicted, referable_probs


# Calculate AUC for referable DR
def calculate_auc(actual, probabilities):
    positive = []
    negative = []
    for i in range(len(actual)):
        if actual[i] >= 2:
            positive.append(probabilities[i])
        else:
            negative.append(probabilities[i])
    if len(positive) == 0 or len(negative) == 0:
        return float("nan")
    correct = 0
    for p in positive:
        for n in negative:
            if p > n:
                correct += 1
            elif p == n:
                correct += 0.5
    return correct / (len(positive) * len(negative))


# Calculate precision, recall and F1 score
def calculate_metrics(actual, predicted, probabilities):
    confusion = []
    for i in range(5):
        row = []
        for j in range(5):
            row.append(0)
        confusion.append(row)
    for i in range(len(actual)):
        confusion[actual[i]][predicted[i]] += 1
    class_metrics = []
    for i in range(5):
        true_positive = confusion[i][i]
        predicted_total = sum(confusion[j][i] for j in range(5))
        actual_total = sum(confusion[i])
        if predicted_total == 0:
            precision = 0
        else:
            precision = true_positive / predicted_total
        if actual_total == 0:
            recall = 0
        else:
            recall = true_positive / actual_total
        if precision + recall == 0:
            f1 = 0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        class_metrics.append({
            "grade": CLASSES[i],
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": actual_total
        })
    # Referable DR means grade 2 or above
    actual_referable = []
    predicted_referable = []
    for i in range(len(actual)):
        actual_referable.append(actual[i] >= 2)
        predicted_referable.append(probabilities[i] >= THRESHOLD)
    tp = 0
    tn = 0
    for i in range(len(actual)):
        if actual_referable[i] and predicted_referable[i]:
            tp += 1
        if not actual_referable[i] and not predicted_referable[i]:
            tn += 1
    total_positive = sum(actual_referable)
    total_negative = len(actual) - total_positive
    sensitivity = tp / max(total_positive, 1)
    specificity = tn / max(total_negative, 1)
    accuracy = sum(
        actual[i] == predicted[i]
        for i in range(len(actual))
    ) / len(actual)
    kappa = calculate_kappa(actual, predicted)
    macro_f1 = sum(
        item["f1"] for item in class_metrics
    ) / 5
    return {
        "images": len(actual),
        "accuracy": accuracy,
        "quadratic_kappa": kappa,
        "macro_f1": macro_f1,
        "referable_threshold": THRESHOLD,
        "referable_sensitivity": sensitivity,
        "referable_specificity": specificity,
        "referable_auc": calculate_auc(actual, probabilities),
        "per_class": class_metrics,
        "confusion_matrix": confusion
    }


# Print results
def print_results(name, report):
    print("\n", name)
    print("Accuracy:", round(report["accuracy"] * 100, 2), "%")
    print("Kappa:", round(report["quadratic_kappa"], 3))
    print("Macro F1:", round(report["macro_f1"], 3))
    print("\nClass-wise results:")
    for item in report["per_class"]:
        print(
            item["grade"],
            "Precision:", round(item["precision"], 3),
            "Recall:", round(item["recall"], 3),
            "F1:", round(item["f1"], 3)
        )
    print("\nConfusion Matrix:")
    for row in report["confusion_matrix"]:
        print(row)
    print("\nReferable DR:")
    print("Sensitivity:", round(report["referable_sensitivity"], 3))
    print("Specificity:", round(report["referable_specificity"], 3))
    print("AUC:", round(report["referable_auc"], 3))


# Save evaluation results
def save_results(model, val_loader, test_loader, device):
    results = {}
    for name, loader in [
        ("validation", val_loader),
        ("test", test_loader)
    ]:
        accuracy, kappa, actual, predicted, probabilities = evaluate_model(
            model, loader, device
        )
        report = calculate_metrics(
            actual, predicted, probabilities
        )
        results[name] = report
        print_results(name, report)
    RESULTS_DIR.mkdir(exist_ok=True)
    # Same name the admin portal reads: <model name>_metrics.json
    output_file = RESULTS_DIR / (MODEL_PATH.stem + "_metrics.json")
    results["model_file"] = MODEL_PATH.name
    results["evaluated_at"] = time.strftime("%Y-%m-%d %H:%M")
    with open(output_file, "w") as file:
        json.dump(results, file, indent=4)
    print("\nResults saved successfully!")


# Main training function
def main():
    device = torch.device(
        "cuda" if torch.cuda.is_available() else "cpu"
    )
    print("Using device:", device)
    # Same random numbers every run, so results can be repeated
    torch.manual_seed(42)
    # Prepare images
    print("\nPreparing images...")
    resize_images()
    # Load datasets
    train_data = RetinaDataset("train", train_transform)
    val_data = RetinaDataset("val", test_transform)
    test_data = RetinaDataset("test", test_transform)
    train_loader = DataLoader(
        train_data,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=0
    )
    val_loader = DataLoader(
        val_data,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0
    )
    test_loader = DataLoader(
        test_data,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=0
    )
    # Create model
    model = create_model().to(device)
    # Loss function and optimizer
    loss_function = nn.CrossEntropyLoss()
    optimizer = optim.AdamW(
        model.parameters(),
        lr=LEARNING_RATE,
        weight_decay=0.0001
    )
    # One-cycle schedule: learning rate warms up, then slowly decreases
    scheduler = optim.lr_scheduler.OneCycleLR(
        optimizer,
        max_lr=LEARNING_RATE,
        epochs=EPOCHS,
        steps_per_epoch=len(train_loader)
    )
    best_kappa = -1
    start_time = time.time()
    # Training starts here
    for epoch in range(EPOCHS):
        model.train()
        total_loss = 0
        for images, labels in train_loader:
            images = images.to(device)
            labels = labels.to(device)
            # Clear previous gradients
            optimizer.zero_grad()
            # Make predictions
            outputs = model(images)
            # Calculate loss
            loss = loss_function(outputs, labels)
            # Backpropagation
            loss.backward()
            # Update model weights
            optimizer.step()
            # Update learning rate after every batch
            scheduler.step()
            total_loss += loss.item()
        average_loss = total_loss / len(train_loader)
        # Check performance on validation data
        val_accuracy, val_kappa, _, _, _ = evaluate_model(
            model, val_loader, device
        )
        print("\nEpoch:", epoch + 1, "/", EPOCHS)
        print("Training Loss:", round(average_loss, 4))
        print("Validation Accuracy:", round(val_accuracy * 100, 2), "%")
        print("Validation Kappa:", round(val_kappa, 4))
        # Save the best model
        if val_kappa > best_kappa:
            best_kappa = val_kappa
            MODEL_PATH.parent.mkdir(exist_ok=True)
            torch.save(model.state_dict(), MODEL_PATH)
            print("Best model saved!")
    print("\nTraining completed!")
    print("Total time:", round((time.time() - start_time) / 60, 2), "minutes")
    # Load the best model
    model.load_state_dict(
        torch.load(MODEL_PATH, map_location=device)
    )
    # Final evaluation
    print("\nFinal Model Evaluation")
    save_results(
        model,
        val_loader,
        test_loader,
        device
    )


if __name__ == "__main__":
    main()
