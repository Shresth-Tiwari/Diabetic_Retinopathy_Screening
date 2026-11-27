# RETINOVA - Diabetic Retinopathy Detection

Explainable deep-learning screening for diabetic retinopathy (DR) from retinal fundus photographs, with patient, doctor and admin portals.

## Features

- **5-grade ICDR classification** (0 No DR → 4 Proliferative) with a ResNet-18 fine-tuned on APTOS 2019.
- **Referable-DR flag**: an image is flagged when P(grade 2–4) ≥ 0.05, tuned on the validation set for high sensitivity.
- **Grad-CAM heatmap** for every prediction, showing which retinal regions drove the grade.
- **Image quality check**: unusable photos (too small, no retinal field, extremely dark/bright) are not graded; the patient is asked to retake them.
- **Follow-up advice** per grade, from the ICDR action table (re-screen in 12 months / 6–12 months / refer within 3 months / urgent / immediate).
- **Patient portal**: latest result in plain language, heatmap, next screening date and full screening history.
- **Doctor portal**: review queue sorted by urgency, original image and heatmap, per-grade probabilities, confirm or override the AI grade with comments, doctor–AI agreement rate.
- **Admin portal**: users and activity, screening volume, review backlog, storage, model test metrics per grade.

## Model performance

Held-out APTOS 2019 test set (366 images), deployed model `models/retinova_resnet18.pth`:

| Metric | Value |
|---|---|
| Accuracy (5 grades) | 85.0% |
| Quadratic weighted kappa | 0.908 |
| Macro F1 | 0.682 |
| Referable DR sensitivity / specificity (threshold 0.05) | 98.5% / 89.5% |
| Referable DR ROC-AUC | 0.989 |

Per-grade recall is lowest for Severe (0.35) and Proliferative (0.55); most of those errors are predicted as Moderate. Full numbers: `results/retinova_resnet18_metrics.json`.

## Installation

Requires Python 3.9+.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Running the application

Double-click `start.bat` (it uses `.venv` if present, checks the packages and opens the browser), or from the project folder:

```bash
python -m uvicorn backend.main:app --reload
```

Open **http://localhost:8000**, sign up, and you are taken to the portal for your role (`/patient`, `/doctor` or `/admin`). Patients upload images from the **Screening** section of the home page.

## Training and evaluation

The dataset lives in `DataBase/` (`train_1.csv`, `valid.csv`, `test.csv` and the matching `*_images` folders).

```bash
python train.py      # train 15 epochs, then evaluate on validation and test
python accuracy.py   # accuracy, precision, recall and F1 of the deployed model
```

Training writes `models/retinova_resnet18_new.pth` (best epoch by validation kappa) and `results/retinova_resnet18_new_metrics.json`, and never overwrites the deployed model. To deploy a new model, rename both files, replacing `retinova_resnet18_new` with `retinova_resnet18`, so the admin portal shows its metrics. `notebooks/main.ipynb` contains the data audit and EDA.

## Project structure

```
backend/                 FastAPI application
  main.py                app setup: routers and static files
  config.py              paths and settings
  database.py            SQLite connection and schema
  ai.py                  image quality check, ResNet18 grading, Grad-CAM
  auth.py                sessions, password hashing, login/signup/logout API
  screenings.py          follow-up advice and screening JSON
  api.py                 upload and portal data API
  pages.py               HTML pages rendered from the templates
frontend/
  templates/             Jinja2 templates: base.html + one per page
  static/css/            base, layout, components, pages
  static/js/             common.js + one script per page
  static/img/            site images
storage/                 app data: retinova.db, uploads/, explanations/ (Grad-CAM)
models/                  trained weights (.pth)
results/                 evaluation metrics (JSON)
DataBase/                APTOS 2019 images and split CSVs
notebooks/               data audit / EDA and its graphs
train.py                 training and evaluation script
start.bat                starts the app on Windows
```

## Built with

FastAPI, Jinja2, PyTorch / torchvision, SQLite, HTML/CSS/JavaScript.

RETINOVA is a research prototype and is not a medical device.
