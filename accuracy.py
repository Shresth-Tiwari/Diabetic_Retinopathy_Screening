import csv
import os
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

# Paths (relative to this file, so it works from any folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "retinova_resnet18.pth")
TEST_CSV = os.path.join(BASE_DIR, "DataBase", "test.csv")
TEST_IMAGES = os.path.join(BASE_DIR, "DataBase", "test_images")

# Load model
model = models.resnet18()
model.fc = nn.Linear(model.fc.in_features, 5)
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()

# Image preprocessing
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406],
                         [0.229, 0.224, 0.225])
])

grades = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]

y_true = []
y_pred = []

# Read test data
with open(TEST_CSV, "r") as f:
    data = csv.DictReader(f)

    for row in data:
        img = Image.open(os.path.join(TEST_IMAGES, row["id_code"] + ".png"))
        img = img.convert("RGB")

        img = transform(img).unsqueeze(0)

        with torch.no_grad():
            output = model(img)
            prediction = output.argmax(1).item()

        y_true.append(int(row["diagnosis"]))
        y_pred.append(prediction)

# Calculate accuracy
correct = 0

for i in range(len(y_true)):
    if y_true[i] == y_pred[i]:
        correct += 1

accuracy = correct / len(y_true)
print("Accuracy:", round(accuracy * 100, 2), "%")

# Calculate precision, recall and F1 score
precisions = []
recalls = []
f1_scores = []

for i in range(5):
    tp = fp = fn = 0

    for j in range(len(y_true)):
        if y_true[j] == i and y_pred[j] == i:
            tp += 1
        elif y_true[j] != i and y_pred[j] == i:
            fp += 1
        elif y_true[j] == i and y_pred[j] != i:
            fn += 1

    precision = tp / (tp + fp) if tp + fp != 0 else 0
    recall = tp / (tp + fn) if tp + fn != 0 else 0

    f1 = 0
    if precision + recall != 0:
        f1 = 2 * precision * recall / (precision + recall)

    print("\nGrade:", grades[i])
    print("Precision:", round(precision, 2))
    print("Recall:", round(recall, 2))
    print("F1 Score:", round(f1, 2))

    precisions.append(precision)
    recalls.append(recall)
    f1_scores.append(f1)

# Average over the 5 grades (macro average)
print("\nAverage")
print("Precision:", round(sum(precisions) / 5, 2))
print("Recall:", round(sum(recalls) / 5, 2))
print("F1 Score:", round(sum(f1_scores) / 5, 2))