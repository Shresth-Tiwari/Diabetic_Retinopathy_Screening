"""Generate the mid-term viva slide deck (PPTX) from the notebook outputs.

Run from the repository root after executing main.ipynb:
    python reports/make_ppt.py
"""
import json
from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
G = ROOT / "graphs"
M = json.loads((ROOT / "results" / "metrics.json").read_text())
OUT = ROOT / "reports" / "Mid_Term_Presentation.pptx"

INK = RGBColor(0x0B, 0x0B, 0x0B)
MUTED = RGBColor(0x52, 0x51, 0x4E)
ACCENT = RGBColor(0x2A, 0x78, 0xD6)
BG = RGBColor(0xFC, 0xFC, 0xFB)
W, H = Inches(13.333), Inches(7.5)

prs = Presentation()
prs.slide_width, prs.slide_height = W, H
BLANK = prs.slide_layouts[6]
pct = lambda x: f"{100 * x:.1f}%"


def base(title, number=True):
    s = prs.slides.add_slide(BLANK)
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.12))
    bar.fill.solid(); bar.fill.fore_color.rgb = ACCENT; bar.line.fill.background()
    tb = s.shapes.add_textbox(Inches(0.6), Inches(0.35), Inches(12), Inches(0.9))
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = title; r.font.size = Pt(30); r.font.bold = True; r.font.color.rgb = INK
    if number:
        nb = s.shapes.add_textbox(Inches(12.3), Inches(7.0), Inches(0.9), Inches(0.4))
        nr = nb.text_frame.paragraphs[0]; nr.alignment = PP_ALIGN.RIGHT
        rr = nr.add_run(); rr.text = str(len(prs.slides)); rr.font.size = Pt(11); rr.font.color.rgb = MUTED
    return s


def text(s, items, x, y, w, h, size=18):
    tf = s.shapes.add_textbox(x, y, w, h).text_frame
    tf.word_wrap = True
    for i, it in enumerate(items):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        sub = it.startswith("-")
        r = para.add_run()
        r.text = ("    - " + it[1:].strip()) if sub else ("• " + it)
        r.font.size = Pt(size - 3 if sub else size)
        r.font.color.rgb = MUTED if sub else INK
        para.space_after = Pt(8)
    return tf


def image(s, name, x, y, max_w, max_h):
    iw, ih = Image.open(G / name).size
    scale = min(max_w / iw, max_h / ih)
    w, h = int(iw * scale), int(ih * scale)
    s.shapes.add_picture(str(G / name), x + (max_w - w) // 2, y + (max_h - h) // 2, w, h)


def notes(s, t):
    s.notes_slide.notes_text_frame.text = t


def stat(s, x, y, value, label):
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(2.9), Inches(1.6))
    box.fill.solid(); box.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    box.line.color.rgb = RGBColor(0xE6, 0xE5, 0xE1)
    tf = box.text_frame
    p1 = tf.paragraphs[0]; p1.alignment = PP_ALIGN.CENTER
    r = p1.add_run(); r.text = value; r.font.size = Pt(34); r.font.bold = True; r.font.color.rgb = ACCENT
    p2 = tf.add_paragraph(); p2.alignment = PP_ALIGN.CENTER
    r = p2.add_run(); r.text = label; r.font.size = Pt(13); r.font.color.rgb = MUTED


# 1. Title
s = base("", number=False)
tb = s.shapes.add_textbox(Inches(0.8), Inches(2.0), Inches(11.7), Inches(3.5)).text_frame
tb.word_wrap = True
r = tb.paragraphs[0].add_run(); r.text = "Explainable AI for Diabetic Retinopathy Screening in Rural India"
r.font.size = Pt(40); r.font.bold = True; r.font.color.rgb = INK
for t, sz in [("Mid-Term Project Review - Prototype", 22), ("", 10),
              ("Shresth Tiwari  |  B.Tech AI & ML, 2nd Year", 18),
              ("Dataset: APTOS 2019 Blindness Detection  |  16 October 2026", 16)]:
    p = tb.add_paragraph(); rr = p.add_run(); rr.text = t; rr.font.size = Pt(sz); rr.font.color.rgb = MUTED
notes(s, "Introduce yourself and the project in one line: a lightweight, explainable deep-learning tool that grades "
         "diabetic retinopathy from a fundus photo and tells a rural health worker whether to refer the patient.")

# 2. Problem
s = base("The problem")
stat(s, Inches(0.8), Inches(1.5), "77 M+", "diabetic adults in India")
stat(s, Inches(3.95), Inches(1.5), "~18%", "of them have DR")
stat(s, Inches(7.1), Inches(1.5), "< 1", "ophthalmologist per 2.5 lakh rural people")
stat(s, Inches(10.25), Inches(1.5), "Silent", "early DR has no symptoms")
text(s, ["DR is a leading cause of preventable blindness - treatable if detected early",
         "Screening needs a trained grader; rural PHCs do not have one",
         "Goal: offline tool for ASHA / PHC staff that grades DR, flags referral, and explains why"],
     Inches(0.8), Inches(3.6), Inches(11.8), Inches(3.2), size=20)
notes(s, "Key point: the bottleneck is not treatment but detection. Early DR is asymptomatic, and there are not enough "
         "specialists in rural India. An AI triage tool can let a health worker screen and refer only those who need it.")

# 3. Objectives
s = base("Objectives & ICDR grading scale")
text(s, ["Audit, explore and preprocess a real Indian fundus dataset",
         "Choose a model that is accurate AND runs on a CPU laptop",
         "Make every prediction explainable (Grad-CAM)",
         "Output: grade + confidence + referral advice + heatmap"],
     Inches(0.6), Inches(1.4), Inches(6.0), Inches(4.5), size=19)
tbl = s.shapes.add_table(6, 3, Inches(6.9), Inches(1.5), Inches(5.9), Inches(3.8)).table
rows = [("Grade", "Finding", "Action"), ("0 No DR", "Healthy", "Re-screen yearly"),
        ("1 Mild", "Microaneurysms only", "Re-screen 6-12 mo"),
        ("2 Moderate", "Haemorrhages, exudates", "Refer < 3 months"),
        ("3 Severe", "4-2-1 rule", "Urgent referral"),
        ("4 Proliferative", "New vessels", "Immediate referral")]
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        c = tbl.cell(i, j); c.text = v
        c.text_frame.paragraphs[0].runs[0].font.size = Pt(14)
notes(s, "Grades 2 and above are 'referable DR' - that binary decision is the most important clinical output.")

# 4. Dataset
s = base("Dataset collection - APTOS 2019")
text(s, ["Source: Kaggle APTOS 2019, Aravind Eye Hospital (India)",
         "3,662 colour fundus images, labelled 0-4 by clinicians",
         "Captured in rural clinics with many different cameras - realistic for our use case",
         "Stratified split: 2,930 train / 366 validation / 366 test"],
     Inches(0.6), Inches(1.4), Inches(5.6), Inches(5), size=18)
image(s, "sample_images.png", Inches(6.3), Inches(1.3), Inches(6.7), Inches(5.6))
notes(s, "Why APTOS: it is Indian data from Aravind, collected in real rural screening camps, so it matches the deployment "
         "population. Split is stratified so every grade has the same share in train/val/test.")

# 5. Data quality
s = base("Data quality: missing values, duplicates, outliers")
text(s, ["Missing labels: 0  |  Duplicate IDs: 0  |  Invalid labels: 0",
         "Missing image files: 0  |  Train-test overlap: 0 (no leakage)",
         "16 camera resolutions (474x358 to 4288x2848 px)",
         "Black border = 21% of pixels on average",
         "Exposure outliers (1.5xIQR): 3 / 500 sampled images",
         "-Kept on purpose: rural cameras produce such images; contrast normalisation reduces their effect"],
     Inches(0.6), Inches(1.4), Inches(5.4), Inches(5.5), size=17)
image(s, "image_stats.png", Inches(6.1), Inches(1.4), Inches(7.0), Inches(3.0))
image(s, "outliers.png", Inches(6.1), Inches(4.5), Inches(7.0), Inches(2.4))
notes(s, "Tabular checks were all clean. For images, outliers are acquisition problems (too dark/bright). I did not delete them "
         "because a deployed model will see such images; instead preprocessing normalises them.")

# 6. EDA
s = base("EDA insights - class imbalance")
image(s, "class_distribution.png", Inches(0.4), Inches(1.3), Inches(6.3), Inches(3.8))
image(s, "class_comparison.png", Inches(6.8), Inches(1.3), Inches(6.2), Inches(3.8))
text(s, ["No DR = 48.9%, Severe = 5.3% -> imbalance 9.3 : 1",
         "Referable DR (grade >= 2) = 40.8% -> balanced binary triage task",
         "Same grade proportions in all splits (stratified); Mild differs from No DR only by tiny microaneurysms"],
     Inches(0.6), Inches(5.3), Inches(12.2), Inches(2), size=16)
notes(s, "Imbalance means plain accuracy can be misleading, so I report macro-F1, QWK and per-class recall, and use class weights.")

# 7. Preprocessing
s = base("Preprocessing & feature engineering")
text(s, ["Crop black border -> retina only",
         "Resize 224x224 (unifies 16 resolutions)",
         "Ben Graham contrast normalisation -> lesions pop out, lighting equalised",
         "MobileNetV2 scaling to [-1, 1]",
         "Augmentation: flips, rotation, zoom",
         "Balanced class weights: Severe 3.8x, No DR 0.41x"],
     Inches(0.6), Inches(1.4), Inches(6.2), Inches(5.5), size=18)
image(s, "preprocessing.png", Inches(7.0), Inches(1.2), Inches(5.9), Inches(5.9))
notes(s, "In deep learning the CNN learns features itself, so feature engineering here means preparing better inputs: "
         "cropping, contrast normalisation and augmentation, plus class weights for imbalance.")

# 8. Model selection
s = base("Model selection & justification")
tbl = s.shapes.add_table(6, 3, Inches(0.6), Inches(1.4), Inches(12.1), Inches(3.9)).table
rows = [("Option", "Problem for our data / deployment", "Decision"),
        ("SVM / Random Forest + hand-crafted features", "Miss tiny lesions; far lower accuracy", "Rejected"),
        ("CNN from scratch", "Overfits on 2,930 images", "Rejected"),
        ("ResNet50 / InceptionV3", "23-25 M params, ~100 MB, slow on CPU", "Rejected"),
        ("EfficientNet-B4 / ViT", "Needs GPU + big data", "Future"),
        ("MobileNetV2 (transfer learning)", "2.3 M params, 8.7 MB, real-time CPU, clean Grad-CAM", "Chosen")]
for i, row in enumerate(rows):
    for j, v in enumerate(row):
        c = tbl.cell(i, j); c.text = v
        c.text_frame.paragraphs[0].runs[0].font.size = Pt(15)
text(s, ["Architecture: MobileNetV2 (ImageNet, frozen) -> GlobalAvgPool -> Dropout -> Dense(5, softmax)",
         "Depthwise-separable convs + inverted residuals: ~8-9x fewer operations than normal convs"],
     Inches(0.6), Inches(5.6), Inches(12.1), Inches(1.6), size=17)
notes(s, "Data characteristics drive the choice: small data -> transfer learning; tiny lesions -> CNN, not hand-crafted features; "
         "PHC laptop without GPU -> light model; explainability -> CNN with a spatial feature map for Grad-CAM.")

# 9. Training
s = base("Training progress")
image(s, "training_curves.png", Inches(0.4), Inches(1.3), Inches(8.4), Inches(4.2))
text(s, ["Phase 1: frozen backbone, train head only",
         "Adam, categorical cross-entropy, 12 epochs",
         "Checkpoint on best val accuracy",
         f"Best val acc {pct(M['best_val_accuracy'])} (epoch {M['best_epoch']})",
         "Val loss flattens after epoch 7 -> next: fine-tuning"],
     Inches(8.9), Inches(1.4), Inches(4.2), Inches(5.5), size=16)
notes(s, "The gap between train and validation stays small, so no severe overfitting. Validation accuracy fluctuates because the "
         "validation set is small (366) and minority grades have only 22-28 images.")

# 10. Results
s = base("Results on held-out test set (366 images)")
stat(s, Inches(0.6), Inches(1.4), f"{M['quadratic_kappa']:.3f}", "Quadratic Weighted Kappa")
stat(s, Inches(0.6), Inches(3.15), pct(M["referable_sensitivity"]), "Referable-DR sensitivity")
stat(s, Inches(0.6), Inches(4.9), f"{M['referable_auc']:.3f}", "Referable-DR ROC-AUC")
image(s, "evaluation.png", Inches(3.7), Inches(1.3), Inches(9.4), Inches(4.3))
text(s, [f"Accuracy {pct(M['test_accuracy'])}  |  Macro-F1 {M['macro_f1']:.3f}  |  Specificity {pct(M['referable_specificity'])}",
         "Errors are mostly between neighbouring grades; Severe / Proliferative recall is the weak point"],
     Inches(3.8), Inches(5.7), Inches(9.3), Inches(1.5), size=15)
notes(s, "QWK is the official APTOS metric: it penalises a prediction more the further it is from the true grade. "
         "For a screening tool the binary referral decision matters most - 92% sensitivity, 94% specificity, AUC 0.98.")

# 11. XAI
s = base("Explainability - Grad-CAM")
image(s, "gradcam.png", Inches(0.4), Inches(1.2), Inches(12.5), Inches(4.6))
text(s, ["Gradient of predicted class w.r.t. last conv map (7x7x1280) -> channel weights -> weighted sum -> heatmap",
         "Lets a doctor check that the decision comes from lesions, not borders or artefacts -> trust & accountability"],
     Inches(0.6), Inches(5.9), Inches(12.2), Inches(1.4), size=15)
notes(s, "Be honest: maps are coarse (7x7) and some are diffuse because the backbone is frozen; fine-tuning and Grad-CAM++ "
         "should sharpen them. This is why XAI is in the title - a black-box grade is not acceptable in healthcare.")

# 12. Prototype
s = base("Prototype output for a PHC health worker")
tf = s.shapes.add_textbox(Inches(0.8), Inches(1.4), Inches(6.2), Inches(5)).text_frame
for i, line in enumerate(['image:      e4e343eaae2a.png', 'grade:      2 (Moderate)', 'confidence: 0.706',
                          'referable:  true', 'action:     Refer to ophthalmologist', '            within 3 months',
                          '+ Grad-CAM heatmap']):
    para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    r = para.add_run(); r.text = line; r.font.name = "Consolas"; r.font.size = Pt(20); r.font.color.rgb = INK
text(s, ["Runs fully offline on CPU", "8.7 MB model - fits on a phone",
         "Next: FastAPI /predict endpoint + simple web UI"],
     Inches(7.3), Inches(1.6), Inches(5.6), Inches(4), size=19)
notes(s, "This is the screen() function in the notebook. It converts the model output into a clinical action.")

# 13. Progress & next steps
s = base("Progress so far & roadmap")
text(s, ["Done: data audit, EDA, outlier analysis, preprocessing pipeline",
         "Done: MobileNetV2 baseline, test evaluation, Grad-CAM, prototype screening function",
         "Next: fine-tune top blocks with Ben Graham inputs + class weights",
         "Next: ordinal regression head + optimised thresholds (raise QWK, Severe recall)",
         "Next: FastAPI service + web UI, TFLite export for offline devices",
         "Challenge: no local GPU -> heavy training on Kaggle / Colab"],
     Inches(0.6), Inches(1.4), Inches(12.2), Inches(5.5), size=19)

# 14. Viva prep
s = base("Anticipated questions")
text(s, ["Why MobileNetV2? - small data + CPU deployment + Grad-CAM; 10x smaller than ResNet50",
         "Why QWK, not accuracy? - grades are ordered; predicting 4 for a 0 is worse than 1 for a 0",
         "How is imbalance handled? - stratified split, class weights, macro-F1 / per-class recall reported",
         "Why keep outliers? - real PHC images look like that; normalise instead of delete",
         "Is Grad-CAM proof the model is right? - No, it shows where it looked; a clinician still verifies",
         "Limitations? - one dataset, weak Severe recall, frozen backbone, no prospective validation"],
     Inches(0.6), Inches(1.4), Inches(12.2), Inches(5.6), size=17)

# 15. Thanks
s = base("Thank you", number=False)
text(s, ["Code & notebook: github.com/Shresth-Tiwari/Diabetic_Retinopathy_Screening",
         "References: APTOS 2019 (Kaggle); Sandler et al. 2018 (MobileNetV2); Selvaraju et al. 2017 (Grad-CAM); "
         "Gulshan et al. 2016 (JAMA)",
         "Questions?"],
     Inches(0.6), Inches(1.6), Inches(12.2), Inches(4), size=20)

OUT.parent.mkdir(exist_ok=True)
prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides))
