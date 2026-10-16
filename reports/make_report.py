"""Generate the mid-term progress report (DOCX) from the notebook outputs.

Run from the repository root after executing main.ipynb:
    python reports/make_report.py
"""
import json
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "graphs"
M = json.loads((ROOT / "results" / "metrics.json").read_text())
OUT = ROOT / "reports" / "Mid_Term_Progress_Report.docx"

doc = Document()
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(11)


def h(text, level=1):
    doc.add_heading(text, level=level)


def p(text, bold=False, italic=False, align=None):
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.bold, run.italic = bold, italic
    if align:
        para.alignment = align
    return para


def bullets(items):
    for it in items:
        doc.add_paragraph(it, style="List Bullet")


def table(rows, header=True, widths=None):
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, r in enumerate(rows):
        for j, v in enumerate(r):
            cell = t.cell(i, j)
            cell.text = str(v)
            if header and i == 0:
                cell.paragraphs[0].runs[0].bold = True
    doc.add_paragraph()
    return t


def fig(name, caption, width=6.3):
    doc.add_picture(str(G / name), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    c = p(caption, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    c.runs[0].font.size = Pt(9)
    c.runs[0].font.color.rgb = RGBColor(0x52, 0x51, 0x4E)


pct = lambda x: f"{100 * x:.1f}%"

# ---------------- Title page ----------------
for _ in range(4):
    doc.add_paragraph()
p("Mid-Term Progress Report", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER).runs[0].font.size = Pt(16)
t = p("Explainable AI for Diabetic Retinopathy Screening in Rural India", bold=True,
      align=WD_ALIGN_PARAGRAPH.CENTER)
t.runs[0].font.size = Pt(22)
p("Semester Project - B.Tech (AI & ML), 2nd Year", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_paragraph()
p("Submitted by: Shresth Tiwari", align=WD_ALIGN_PARAGRAPH.CENTER)
p("Roll No.: ____________        Guide: ____________", align=WD_ALIGN_PARAGRAPH.CENTER)
p("Date: 16 October 2026", align=WD_ALIGN_PARAGRAPH.CENTER)
p("Code: github.com/Shresth-Tiwari/Diabetic_Retinopathy_Screening", align=WD_ALIGN_PARAGRAPH.CENTER)
doc.add_page_break()

# ---------------- Abstract ----------------
h("Abstract")
p("Diabetic Retinopathy (DR) is a leading cause of preventable blindness in India, home to more than 77 million "
  "diabetic adults, while rural areas have fewer than one ophthalmologist per 250,000 people. This project builds "
  "a lightweight and explainable deep-learning screening tool that grades colour fundus photographs on the 5-level "
  "ICDR scale and shows the clinician where in the retina the evidence lies. Using the APTOS 2019 dataset "
  "(3,662 images from Aravind Eye Hospital), we audited and explored the data, designed a preprocessing pipeline, "
  "trained a MobileNetV2 transfer-learning baseline (8.7 MB, CPU-friendly) and added Grad-CAM explanations. "
  f"On a held-out test set of 366 images the prototype reaches {pct(M['test_accuracy'])} accuracy, a Quadratic "
  f"Weighted Kappa of {M['quadratic_kappa']:.3f}, and for the clinically important referable-DR decision "
  f"(grade >= 2) a sensitivity of {pct(M['referable_sensitivity'])}, specificity of "
  f"{pct(M['referable_specificity'])} and ROC-AUC of {M['referable_auc']:.3f}.")

# ---------------- 1. Introduction ----------------
h("1. Problem Statement and Motivation")
bullets([
    "DR damages retinal blood vessels; early stages are symptom-free, so patients arrive only after vision loss.",
    "Screening needs a trained grader; rural Primary Health Centres (PHCs) rarely have one.",
    "Goal: a tool that a health worker can run offline on a normal laptop with a low-cost fundus camera, that "
    "(a) grades DR severity, (b) flags patients needing referral, and (c) explains its decision with a heatmap so "
    "that doctors can trust or override it.",
])
h("1.1 Objectives", 2)
bullets([
    "Collect, audit and explore a real Indian fundus dataset.",
    "Build a preprocessing pipeline robust to different cameras and lighting.",
    "Select and justify a model that is accurate and deployable on CPU / edge hardware.",
    "Add explainability (Grad-CAM) to every prediction.",
    "Later phase: fine-tuning, a FastAPI service and a simple screening UI.",
])

# ---------------- 2. Dataset ----------------
h("2. Dataset Collection")
p("Source: APTOS 2019 Blindness Detection (Kaggle), provided by the Asia Pacific Tele-Ophthalmology Society and "
  "Aravind Eye Hospital, Madurai. Images were captured in rural Indian clinics with different fundus cameras, "
  "which makes the data a realistic proxy for the target deployment. Each image is labelled by clinicians on the "
  "ICDR scale: 0 No DR, 1 Mild, 2 Moderate, 3 Severe, 4 Proliferative DR. The 3,662 labelled images were split "
  "stratified into training (80%), validation (10%) and test (10%) sets.")
table([
    ["Split", "Images", "No DR", "Mild", "Moderate", "Severe", "Proliferative"],
    ["Train", "2,930", "1,434", "300", "808", "154", "234"],
    ["Validation", "366", "172", "40", "104", "22", "28"],
    ["Test", "366", "199", "30", "87", "17", "33"],
])

# ---------------- 3. Preprocessing ----------------
h("3. Data Quality, Preprocessing and Feature Engineering")
h("3.1 Missing values, duplicates and leakage", 2)
p("Every split was checked for missing labels, duplicate image IDs, labels outside 0-4, CSV rows without an image "
  "file, and image IDs shared between splits. All checks returned zero, so no rows had to be imputed or dropped, "
  "and there is no train/test leakage.")
table([
    ["Check", "Train", "Validation", "Test"],
    ["Missing values", "0", "0", "0"],
    ["Duplicate IDs", "0", "0", "0"],
    ["Invalid labels", "0", "0", "0"],
    ["Missing image files", "0", "0", "0"],
    ["Overlap with other splits", "0", "0", "0"],
])
h("3.2 Outliers", 2)
p("For images, 'outliers' are mostly acquisition problems. A stratified sample of 500 training images was profiled "
  "for resolution, mean retina brightness, contrast and black-border area. Resolution ranges from 474x358 to "
  "4288x2848 px across 16 different camera formats, and the black border takes on average 21% of the image. "
  "Using the 1.5xIQR rule on brightness, 3 of 500 images (0.6%) are exposure outliers (very dark or very bright).")
p("Decision: outliers are kept, not removed. Poorly lit images are exactly what a rural PHC camera will produce, "
  "so the model must handle them; contrast normalisation reduces their effect.")
fig("image_stats.png", "Figure 1. Camera resolutions and retina brightness per grade (dashed = IQR outlier fence).")
fig("outliers.png", "Figure 2. Darkest and brightest sampled images (exposure outliers).")
h("3.3 Preprocessing pipeline", 2)
bullets([
    "Circular crop - remove the black background so the network sees retina, not border.",
    "Resize to 224x224 - the MobileNetV2 input size; also unifies 16 different resolutions.",
    "Ben Graham local-contrast normalisation (subtract Gaussian-blurred copy) - equalises illumination and "
    "highlights microaneurysms and exudates (implemented and visualised; to be used in the fine-tuning phase).",
    "MobileNetV2 preprocess_input - scales pixels to [-1, 1] as expected by the ImageNet weights.",
    "Augmentation (training only) - random horizontal/vertical flips, rotation and zoom; a fundus has no fixed "
    "orientation, so this multiplies the effective data without changing the label.",
])
fig("preprocessing.png", "Figure 3. Raw image, cropped/resized image and Ben Graham enhanced image.", width=5.2)
h("3.4 Feature engineering for imbalance", 2)
p("The training set is imbalanced 9.3:1 (No DR 48.9% vs Severe 5.3%). Balanced class weights "
  "(No DR 0.41, Mild 1.95, Moderate 0.73, Severe 3.81, Proliferative 2.50) make mistakes on rare, "
  "sight-threatening grades cost more during training. For deep CNNs the 'features' are learned by the "
  "convolutional layers; our engineering effort therefore goes into cleaner inputs (crop, contrast, augmentation) "
  "rather than hand-crafted features.")

# ---------------- 4. EDA ----------------
h("4. Exploratory Data Analysis - Insights")
fig("class_distribution.png", "Figure 4. Training class distribution.", width=5.2)
fig("class_comparison.png", "Figure 5. Grade distribution is consistent across train / validation / test.", width=5.5)
fig("sample_images.png", "Figure 6. Random training images for each grade.")
bullets([
    "Strong imbalance: half the images are healthy; Severe and Proliferative together are only 13%.",
    "40.8% of training images are referable DR (grade >= 2) - a balanced binary problem for triage.",
    "Splits are stratified - each grade has the same share in train, validation and test.",
    "Large variation in resolution, field of view and illumination across clinics -> preprocessing is essential.",
    "Healthy retinas are slightly brighter on average; diseased images show yellow exudates, red haemorrhages "
    "and, in grade 4, new vessels and laser scars.",
    "Mild DR differs from No DR only by tiny microaneurysms (a few pixels at 224x224), which explains why Mild "
    "is the hardest class.",
])

# ---------------- 5. Model ----------------
h("5. Methodology - Model Selection and Justification")
p("Characteristics of our data that drive the choice: (1) only 2,930 training images, (2) small, local lesions, "
  "(3) class imbalance, (4) deployment target is a CPU laptop/tablet in a PHC with unreliable internet, "
  "(5) the decision must be explainable.")
table([
    ["Approach", "Pros", "Cons for this project", "Decision"],
    ["SVM / Random Forest on hand-crafted features", "Simple, fast, interpretable features",
     "Cannot capture tiny lesions; much lower accuracy on fundus benchmarks", "Rejected"],
    ["CNN from scratch", "Full control", "Overfits on 2,930 images", "Rejected"],
    ["ResNet50 / InceptionV3", "Strong accuracy", "23-25M params, ~100 MB, slow on CPU", "Rejected"],
    ["EfficientNet-B4 / Vision Transformer", "State of the art on APTOS",
     "Needs GPU and large data; ViT is data-hungry", "Future work"],
    ["MobileNetV2 + transfer learning", "2.3M params, 8.7 MB, real-time on CPU; ImageNet features; clean Grad-CAM",
     "Slightly lower ceiling than large models", "Chosen"],
])
h("5.1 Architecture", 2)
bullets([
    "Input 224x224x3 -> MobileNetV2 backbone (ImageNet weights, frozen) -> 7x7x1280 feature map.",
    "GlobalAveragePooling2D -> Dropout -> Dense(5, softmax).",
    "Total parameters 2,277,201 (8.69 MB); trainable head 6,405 parameters.",
    "Why it is efficient: depthwise-separable convolutions and inverted residual blocks need ~8-9x fewer "
    "operations than standard convolutions.",
])
h("5.2 Training setup", 2)
bullets([
    "Loss: categorical cross-entropy; optimiser: Adam (lr 1e-3); batch size 32; 12 epochs.",
    "Model checkpoint on best validation accuracy; per-epoch metrics logged to training_log.csv.",
    "Phase 1 (done): frozen backbone - feature extraction. Phase 2 (next): unfreeze top blocks and fine-tune with "
    "a low learning rate, Ben Graham inputs and class weights.",
])
fig("training_curves.png", f"Figure 7. Learning curves. Best validation accuracy {pct(M['best_val_accuracy'])} at epoch {M['best_epoch']}.")

# ---------------- 6. Results ----------------
h("6. Results on the Held-out Test Set")
table([
    ["Metric", "Value", "Meaning"],
    ["Accuracy (5-class)", pct(M["test_accuracy"]), "Exact grade correct"],
    ["Macro F1", f"{M['macro_f1']:.3f}", "Average over grades, treats rare grades equally"],
    ["Quadratic Weighted Kappa", f"{M['quadratic_kappa']:.3f}", "Official APTOS metric; > 0.8 = strong agreement"],
    ["Referable DR sensitivity", pct(M["referable_sensitivity"]), "Sick patients correctly referred"],
    ["Referable DR specificity", pct(M["referable_specificity"]), "Healthy patients correctly not referred"],
    ["Referable DR ROC-AUC", f"{M['referable_auc']:.3f}", "Threshold-independent separability"],
])
pc = M["per_class"]
table([["Grade", "Precision", "Recall", "F1", "Support"]] + [
    [g, f"{pc[g]['precision']:.2f}", f"{pc[g]['recall']:.2f}", f"{pc[g]['f1-score']:.2f}", int(pc[g]["support"])]
    for g in ["No DR", "Mild", "Moderate", "Severe", "Proliferative DR"]
])
fig("evaluation.png", "Figure 8. Confusion matrix and referable-DR ROC curve on the test set.")
p("Interpretation: the model is excellent at separating healthy from diseased eyes (No DR recall 96%) and at the "
  "referral decision (AUC 0.98), which is the main job of a screening tool. Most errors are between neighbouring "
  "grades (e.g. Severe vs Proliferative), which the high QWK reflects. Severe and Proliferative recall is still low "
  "because they are rare and the backbone is frozen - the main target of the next phase.")

# ---------------- 7. XAI ----------------
h("7. Explainability with Grad-CAM")
p("Grad-CAM takes the gradient of the predicted class score with respect to the last convolutional feature map "
  "(7x7x1280), averages it per channel to get importance weights, and forms a weighted sum of the feature maps. "
  "The result, upsampled and overlaid on the image, shows which retinal regions drove the prediction.")
fig("gradcam.png", "Figure 9. Grad-CAM heatmaps for one test image of each grade.")
bullets([
    "Heatmaps fall mostly inside the retina and, for several diseased eyes, over exudate / haemorrhage regions; "
    "some maps are diffuse or touch the image edge - a known effect of a frozen backbone that fine-tuning should sharpen.",
    "Heatmaps let a doctor quickly verify or reject a prediction - essential for trust and accountability.",
    "Limitation: at 7x7 resolution the maps are coarse; finer methods (Grad-CAM++, Integrated Gradients) are planned.",
])
p("Prototype output: a screen(image) function returns grade, confidence, referral advice (e.g. 'Refer to "
  "ophthalmologist within 3 months') and the class probabilities, together with the heatmap.")

# ---------------- 8. Status ----------------
h("8. Progress Summary")
table([
    ["Task", "Status"],
    ["Literature review and problem definition", "Completed"],
    ["Dataset collection and train/val/test split", "Completed"],
    ["Data quality audit and outlier analysis", "Completed"],
    ["EDA and visualisation", "Completed"],
    ["Preprocessing pipeline (crop, resize, Ben Graham, augmentation, class weights)", "Completed"],
    ["Baseline MobileNetV2 training", "Completed"],
    ["Test-set evaluation (QWK, sensitivity, specificity, AUC)", "Completed"],
    ["Grad-CAM explainability", "Completed (prototype)"],
    ["Fine-tuning + ordinal head + threshold optimisation", "Planned"],
    ["FastAPI backend + screening web UI", "Planned"],
    ["TFLite export / offline edge deployment", "Planned"],
])
h("9. Challenges Faced")
bullets([
    "No GPU on the local machine (TensorFlow >= 2.11 has no native Windows GPU support) - training done with a "
    "frozen backbone; heavy experiments will move to Kaggle/Colab GPUs.",
    "Class imbalance - handled with class weights and stratified splits; more work needed for Severe.",
    "Heterogeneous images (16 camera resolutions, varying exposure) - handled with cropping, resizing and contrast normalisation.",
    "Label noise between neighbouring grades is known for APTOS - QWK used because it tolerates near-misses.",
])
h("10. Plan for the Remaining Semester")
bullets([
    "Fine-tune top MobileNetV2 blocks; compare with EfficientNet-B0 at similar size.",
    "Treat grading as ordinal (regression + optimised thresholds) to improve QWK and Severe recall.",
    "Test-time augmentation and probability calibration for reliable confidence scores.",
    "FastAPI REST endpoint (/predict returns grade, confidence, referral and Grad-CAM image) and a simple web page.",
    "Export to TensorFlow Lite for offline use on low-cost devices.",
])
h("References")
for r in [
    "APTOS 2019 Blindness Detection, Kaggle. https://www.kaggle.com/c/aptos2019-blindness-detection",
    "Sandler M. et al., MobileNetV2: Inverted Residuals and Linear Bottlenecks, CVPR 2018.",
    "Selvaraju R. R. et al., Grad-CAM: Visual Explanations from Deep Networks via Gradient-based Localization, ICCV 2017.",
    "Gulshan V. et al., Development and Validation of a Deep Learning Algorithm for Detection of Diabetic Retinopathy, JAMA 2016.",
    "Wilkinson C. P. et al., Proposed International Clinical Diabetic Retinopathy Severity Scales, Ophthalmology 2003.",
    "Graham B., Kaggle Diabetic Retinopathy Detection competition report, 2015.",
]:
    doc.add_paragraph(r, style="List Number")

OUT.parent.mkdir(exist_ok=True)
doc.save(OUT)
print("saved", OUT)
