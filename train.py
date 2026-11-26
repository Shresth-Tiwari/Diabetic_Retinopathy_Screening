"""
RETINOVA - ResNet18 training script.

Fine-tunes an ImageNet-pretrained ResNet18 on the retina images in DataBase/
for 5-class diabetic retinopathy grading (0 = No DR ... 4 = Proliferative).

Preprocessing matches backend/ai.py exactly:
    Resize((224, 224)) -> ToTensor -> ImageNet mean/std

Usage:
    python train.py                       # full training (default 15 epochs)
    python train.py --epochs 5            # shorter run
    python train.py --evaluate models/retinova_resnet18.pth
                                          # evaluate an existing model, no training

Output:
    models/retinova_resnet18_new.pth      (best epoch by validation kappa)
    results/<model name>_metrics.json     (val/test metrics, shown in the admin portal)

The existing models/retinova_resnet18.pth is never overwritten. To use the
new model in the app, rename it to retinova_resnet18.pth.
"""

import argparse
import csv
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import models, transforms


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "DataBase"
CACHE_DIR = DATA_DIR / "cache_224"
OUTPUT_PATH = BASE_DIR / "models" / "retinova_resnet18_new.pth"
RESULTS_DIR = BASE_DIR / "results"
REFERABLE_THRESHOLD = 0.05  # keep in sync with backend/main.py

SPLITS = {
    "train": ("train_1.csv", "train_images"),
    "val": ("valid.csv", "val_images"),
    "test": ("test.csv", "test_images"),
}

DR_CLASSES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"]
IMAGE_SIZE = 224
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


# =========================================================
# DATA
# =========================================================

def read_split(split):
    csv_name, _ = SPLITS[split]
    with open(DATA_DIR / csv_name, newline="") as f:
        return [(r["id_code"], int(r["diagnosis"])) for r in csv.DictReader(f)]


def _resize_one(job):
    src, dst = job
    if not dst.exists():
        image = Image.open(src).convert("RGB")
        image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BILINEAR).save(dst)


def build_cache():
    """Resize the original images (up to 3000 px, ~6 GB) to 224x224 once.

    Decoding the full-size PNGs every epoch would make CPU training several
    times slower. Resizing to 224x224 is the same thing main.py does at
    inference time, so training and the app see identical inputs.
    """
    jobs = []
    for split, (_, image_dir) in SPLITS.items():
        out_dir = CACHE_DIR / split
        out_dir.mkdir(parents=True, exist_ok=True)
        for image_id, _ in read_split(split):
            jobs.append((DATA_DIR / image_dir / f"{image_id}.png",
                         out_dir / f"{image_id}.png"))

    todo = [j for j in jobs if not j[1].exists()]
    if not todo:
        return

    print(f"Resizing {len(todo)} images to {IMAGE_SIZE}x{IMAGE_SIZE} (one-time)...")
    start = time.time()
    with ProcessPoolExecutor() as pool:
        for i, _ in enumerate(pool.map(_resize_one, todo, chunksize=16), 1):
            if i % 250 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}")
    print(f"Cache ready in {time.time() - start:.0f}s\n")


class RetinaDataset(Dataset):

    def __init__(self, split, transform):
        self.items = read_split(split)
        self.folder = CACHE_DIR / split
        self.transform = transform

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        image_id, label = self.items[index]
        image = Image.open(self.folder / f"{image_id}.png").convert("RGB")
        return self.transform(image), label


train_transform = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomVerticalFlip(),
    transforms.RandomRotation(180),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])

eval_transform = transforms.Compose([
    transforms.ToTensor(),
    transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
])


# =========================================================
# MODEL
# =========================================================

def build_model():
    # Same architecture as backend/main.py, starting from ImageNet weights
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model.fc = nn.Linear(model.fc.in_features, len(DR_CLASSES))
    return model


# =========================================================
# METRICS
# =========================================================

def quadratic_kappa(y_true, y_pred, n=len(DR_CLASSES)):
    """Quadratic weighted kappa - the standard metric for DR grading."""
    observed = torch.zeros(n, n)
    for t, p in zip(y_true, y_pred):
        observed[t, p] += 1
    weights = torch.tensor([[(i - j) ** 2 for j in range(n)] for i in range(n)],
                           dtype=torch.float) / (n - 1) ** 2
    expected = torch.outer(observed.sum(1), observed.sum(0)) / observed.sum()
    return 1 - (weights * observed).sum().item() / (weights * expected).sum().item()


@torch.no_grad()
def evaluate(model, loader, device):
    model.eval()
    labels, preds, referable_probs = [], [], []
    for images, targets in loader:
        probs = torch.softmax(model(images.to(device)), dim=1).cpu()
        labels += targets.tolist()
        preds += probs.argmax(1).tolist()
        referable_probs += probs[:, 2:].sum(1).tolist()
    accuracy = sum(p == t for p, t in zip(preds, labels)) / len(labels)
    return accuracy, quadratic_kappa(labels, preds), labels, referable_probs, preds


def referable_auc(labels, referable_probs):
    """ROC-AUC for referable DR: chance a referable image scores above a non-referable one."""
    pos = [p for p, t in zip(referable_probs, labels) if t >= 2]
    neg = [p for p, t in zip(referable_probs, labels) if t < 2]
    if not pos or not neg:
        return float("nan")
    wins = sum((p > q) + 0.5 * (p == q) for p in pos for q in neg)
    return wins / (len(pos) * len(neg))


def full_report(labels, preds, referable_probs, threshold=REFERABLE_THRESHOLD):
    """Per-class precision/recall/F1, confusion matrix and referable-DR metrics."""
    n = len(DR_CLASSES)
    confusion = [[0] * n for _ in range(n)]
    for t, p in zip(labels, preds):
        confusion[t][p] += 1

    per_class = []
    for c in range(n):
        tp = confusion[c][c]
        predicted = sum(confusion[r][c] for r in range(n))
        actual = sum(confusion[c])
        precision = tp / predicted if predicted else 0.0
        recall = tp / actual if actual else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({"grade": DR_CLASSES[c], "precision": precision,
                          "recall": recall, "f1": f1, "support": actual})

    is_referable = [t >= 2 for t in labels]
    flagged = [p >= threshold for p in referable_probs]
    tp = sum(f and r for f, r in zip(flagged, is_referable))
    tn = sum(not f and not r for f, r in zip(flagged, is_referable))

    return {
        "images": len(labels),
        "accuracy": sum(p == t for p, t in zip(preds, labels)) / len(labels),
        "quadratic_kappa": quadratic_kappa(labels, preds),
        "macro_f1": sum(c["f1"] for c in per_class) / n,
        "referable_threshold": threshold,
        "referable_sensitivity": tp / max(sum(is_referable), 1),
        "referable_specificity": tn / max(len(labels) - sum(is_referable), 1),
        "referable_auc": referable_auc(labels, referable_probs),
        "per_class": per_class,
        "confusion_matrix": confusion,
    }


def print_report(name, report):
    print(f"\n{name}: accuracy {report['accuracy']:.1%}, "
          f"quadratic kappa {report['quadratic_kappa']:.3f}, "
          f"macro F1 {report['macro_f1']:.3f}")
    print(f"  Referable DR @ {report['referable_threshold']}: "
          f"sensitivity {report['referable_sensitivity']:.1%}, "
          f"specificity {report['referable_specificity']:.1%}, "
          f"AUC {report['referable_auc']:.3f}")
    print("  grade           precision  recall    f1  support")
    for c in report["per_class"]:
        print(f"  {c['grade']:<14} {c['precision']:>10.2f} {c['recall']:>7.2f} "
              f"{c['f1']:>5.2f} {c['support']:>8}")
    print("  confusion matrix (rows = true grade, columns = predicted):")
    for row in report["confusion_matrix"]:
        print("   ", " ".join(f"{v:>4}" for v in row))


def evaluate_and_save(model, val_loader, test_loader, device, model_path, extra=None):
    """Evaluate on validation + test, print the full report and save it next to results/."""
    reports = {}
    for name, loader in (("validation", val_loader), ("test", test_loader)):
        _, _, labels, referable, preds = evaluate(model, loader, device)
        if name == "validation":
            print_referable_table(labels, referable)
        reports[name] = full_report(labels, preds, referable)
        print_report(name.capitalize(), reports[name])

    metrics_path = RESULTS_DIR / f"{Path(model_path).stem}_metrics.json"
    RESULTS_DIR.mkdir(exist_ok=True)
    metrics_path.write_text(json.dumps({
        "model_file": Path(model_path).name,
        "architecture": "ResNet18",
        "input_size": IMAGE_SIZE,
        "train_images": len(read_split("train")),
        "evaluated_at": time.strftime("%Y-%m-%d %H:%M"),
        **(extra or {}),
        **reports,
    }, indent=2))
    print(f"\nMetrics written to {metrics_path}")


def print_referable_table(labels, referable_probs):
    """Sensitivity/specificity for referable DR (classes 2-4) per threshold,
    to choose REFERABLE_THRESHOLD in backend/main.py."""
    is_referable = [t >= 2 for t in labels]
    print("\nReferable DR threshold (validation set):")
    print("  threshold  sensitivity  specificity")
    for threshold in [0.02, 0.05, 0.1, 0.2, 0.3, 0.5]:
        flagged = [p >= threshold for p in referable_probs]
        tp = sum(f and r for f, r in zip(flagged, is_referable))
        tn = sum(not f and not r for f, r in zip(flagged, is_referable))
        sens = tp / max(sum(is_referable), 1)
        spec = tn / max(len(is_referable) - sum(is_referable), 1)
        print(f"  {threshold:>9.2f}  {sens:>11.1%}  {spec:>11.1%}")


# =========================================================
# TRAINING
# =========================================================

def main():
    parser = argparse.ArgumentParser(description="Train the RETINOVA ResNet18 model")
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--evaluate", metavar="MODEL_PATH",
                        help="evaluate an existing model on val/test and exit")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(42)

    build_cache()

    train_loader = DataLoader(RetinaDataset("train", train_transform),
                              batch_size=args.batch_size, shuffle=True,
                              num_workers=args.workers, persistent_workers=args.workers > 0)
    val_loader = DataLoader(RetinaDataset("val", eval_transform),
                            batch_size=args.batch_size, num_workers=args.workers)
    test_loader = DataLoader(RetinaDataset("test", eval_transform),
                             batch_size=args.batch_size, num_workers=args.workers)

    if args.evaluate:
        model = build_model().to(device)
        model.load_state_dict(torch.load(args.evaluate, map_location=device))
        evaluate_and_save(model, val_loader, test_loader, device, args.evaluate)
        return

    model = build_model().to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(
        optimizer, max_lr=args.lr, epochs=args.epochs, steps_per_epoch=len(train_loader))

    print(f"Training on {device} for {args.epochs} epochs "
          f"({len(train_loader.dataset)} train / {len(val_loader.dataset)} val images)\n")

    best_kappa = -1.0
    total_start = time.time()

    for epoch in range(1, args.epochs + 1):
        model.train()
        epoch_start = time.time()
        running_loss = 0.0

        for step, (images, targets) in enumerate(train_loader, 1):
            images, targets = images.to(device), targets.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), targets)
            loss.backward()
            optimizer.step()
            scheduler.step()
            running_loss += loss.item()
            if step % 20 == 0:
                print(f"  epoch {epoch} batch {step}/{len(train_loader)} "
                      f"loss {running_loss / step:.3f}", end="\r")

        val_acc, val_kappa, _, _, _ = evaluate(model, val_loader, device)
        saved = ""
        if val_kappa > best_kappa:
            best_kappa = val_kappa
            OUTPUT_PATH.parent.mkdir(exist_ok=True)
            torch.save(model.state_dict(), OUTPUT_PATH)
            saved = "  <- saved"

        print(f"Epoch {epoch:>2}/{args.epochs}  loss {running_loss / len(train_loader):.3f}  "
              f"val acc {val_acc:.1%}  val kappa {val_kappa:.3f}  "
              f"({(time.time() - epoch_start) / 60:.1f} min){saved}")

    print(f"\nTotal training time: {(time.time() - total_start) / 60:.1f} min")

    model.load_state_dict(torch.load(OUTPUT_PATH, map_location=device))
    evaluate_and_save(model, val_loader, test_loader, device, OUTPUT_PATH,
                      {"epochs": args.epochs, "best_val_kappa": best_kappa})
    print(f"Best model saved to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
